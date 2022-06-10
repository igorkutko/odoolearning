import base64
import binascii
import collections
import unicodedata

import datetime
import io
import logging
import psycopg2
import operator
import re
import requests

from PIL import Image

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat

FIELDS_RECURSION_LIMIT = 3
ERROR_PREVIEW_BYTES = 200
DEFAULT_IMAGE_TIMEOUT = 3
DEFAULT_IMAGE_MAXBYTES = 10 * 1024 * 1024
DEFAULT_IMAGE_REGEX = r"^(?:http|https)://"
DEFAULT_IMAGE_CHUNK_SIZE = 32768
IMAGE_FIELDS = ["icon", "image", "logo", "picture"]

_logger = logging.getLogger(__name__)


class ImportValidationError(Exception):
    """
    This class is made to correctly format all the different error types that
    can occur during the pre-validation of the import that is made before
    calling the data loading itself. The Error data structure is meant to copy
    the one of the errors raised during the data loading. It simplifies the
    error management at client side as all errors can be treated the same way.

    This exception is typically raised when there is an error during data
    parsing (image, int, dates, etc..) or if the user did not select at least
    one field to map with a column.
    """
    def __init__(self, message, **kwargs):
        super().__init__(message)
        self.type = kwargs.get('error_type', 'error')
        self.message = message
        self.record = False
        self.not_matching_error = True
        self.field_path = [kwargs['field']] if kwargs.get('field') else False
        self.field_type = kwargs.get('field_type')


class DataImport(models.TransientModel):
    _name = 'ata_parser.data_import'
    _description = 'Import data from params to model'

    res_model = fields.Char('Model')

    @api.model
    def _map_import_data(self, data_rows, data_fields, options):
        """ Extracts the input BaseModel and fields list (with
            ``False``-y placeholders for fields to *not* import) into a
            format Model.import_data can use: a fields list without holes
            and the precisely matching data matrix

            :param list(str|bool): fields
            :returns: (data, fields)
            :rtype: (list(list(str)), list(str))
            :raises ValueError: in case the import data could not be converted
        """
        # Get indices for non-empty fields
        indices = [index for index, field in enumerate(data_fields) if field]
        if not indices:
            raise ImportValidationError(_("You must configure at least one field to import"))

        # If only one index, itemgetter will return an atom rather
        # than a 1-tuple
        if len(indices) == 1:
            mapper = lambda row: [row[indices[0]]]
        else:
            mapper = operator.itemgetter(*indices)

        # Get only list of actually imported fields
        import_fields = [f for f in data_fields if f]

        data = [list(row) for row in map(mapper, data_rows) if any(row)]

        # slicing needs to happen after filtering out empty rows as the
        # data offsets from load are post-filtering
        return data[options.get('skip', 0):], import_fields

    def _parse_import_data(self, data, import_fields, options):
        """ Lauch first call to :meth:`_parse_import_data_recursive` with an
        empty prefix. :meth:`_parse_import_data_recursive` will be run
        recursively for each relational field.
        """
        return self._parse_import_data_recursive(self.res_model, '', data, import_fields, options)

    def _parse_import_data_recursive(self, model, prefix, data, import_fields, options):
        # Get fields of type date/datetime
        all_fields = self.env[model].fields_get()
        for name, field in all_fields.items():
            name = prefix + name
            # Check if the field is in import_field and is a relational (followed by /)
            # Also verify that the field name exactly match the import_field at the correct level.
            if any(name + '/' in import_field and name == import_field.split('/')[prefix.count('/')] for import_field in import_fields):
                # Recursive call with the relational as new model and add the field name to the prefix
                self._parse_import_data_recursive(field['relation'], name + '/', data, import_fields, options)
            elif field['type'] in ('date', 'datetime') and name in import_fields:
                # Parse date, datetime values from input data
                index = import_fields.index(name)
                self._parse_date_from_data(data, index, name, field['type'], options)
            elif field['type'] in ('float', 'monetary') and name in import_fields:
                # Parse float, monetary from input data
                # Sometimes float values have currency symbol or () to denote a negative value
                # We should be able to manage both case
                index = import_fields.index(name)
                self._parse_float_from_data(data, index, name, options)
            elif field['type'] == 'binary' and field.get('attachment') and any(f in name for f in IMAGE_FIELDS) and name in import_fields:
                index = import_fields.index(name)

                with requests.Session() as session:
                    session.stream = True

                    for num, line in enumerate(data):
                        if re.match(config.get("import_image_regex", DEFAULT_IMAGE_REGEX), line[index]):
                            if not self.env.user._can_import_remote_urls():
                                raise ImportValidationError(
                                    _("You can not import images via URL, check with your administrator or support for the reason."),
                                    field=name, field_type=field['type']
                                )

                            line[index] = self._import_image_by_url(line[index], session, name, num)
                        else:
                            try:
                                base64.b64decode(line[index], validate=True)
                            except binascii.Error:
                                raise ImportValidationError(
                                    _("Found invalid image data, images should be imported as either URLs or base64-encoded data."),
                                    field=name, field_type=field['type']
                                )

        return data

    def _parse_date_from_data(self, data, index, name, field_type, options):
        dt = datetime.datetime
        fmt = fields.Date.to_string if field_type == 'date' else fields.Datetime.to_string
        d_fmt = options.get('date_format')
        dt_fmt = options.get('datetime_format')
        for num, line in enumerate(data):
            if not line[index]:
                continue

            v = line[index].strip()
            try:
                # first try parsing as a datetime if it's one
                if dt_fmt and field_type == 'datetime':
                    try:
                        line[index] = fmt(dt.strptime(v, dt_fmt))
                        continue
                    except ValueError:
                        pass
                # otherwise try parsing as a date whether it's a date
                # or datetime
                line[index] = fmt(dt.strptime(v, d_fmt))
            except ValueError as e:
                raise ImportValidationError(
                    _("Column %s contains incorrect values. Error in line %d: %s") % (name, num + 1, e),
                    field=name, field_type=field_type
                )
            except Exception as e:
                raise ImportValidationError(
                    _("Error Parsing Date [%s:L%d]: %s") % (name, num + 1, e),
                    field=name, field_type=field_type
                )

    @api.model
    def _parse_float_from_data(self, data, index, name, options):
        for line in data:
            line[index] = line[index].strip()
            if not line[index]:
                continue
            thousand_separator, decimal_separator = self._infer_separators(line[index], options)

            if 'E' in line[index] or 'e' in line[index]:
                tmp_value = line[index].replace(thousand_separator, '.')
                try:
                    tmp_value = '{:f}'.format(float(tmp_value))
                    line[index] = tmp_value
                    thousand_separator = ' '
                except Exception:
                    pass

            line[index] = line[index].replace(thousand_separator, '').replace(decimal_separator, '.')
            old_value = line[index]
            line[index] = self._remove_currency_symbol(line[index])
            if line[index] is False:
                raise ImportValidationError(_("Column %s contains incorrect values (value: %s)", name, old_value), field=name)

    def _infer_separators(self, value, options):
        """ Try to infer the shape of the separators: if there are two
        different "non-numberic" characters in the number, the
        former/duplicated one would be grouping ("thousands" separator) and
        the latter would be the decimal separator. The decimal separator
        should furthermore be unique.
        """
        # can't use \p{Sc} using re so handroll it
        non_number = [
            # any character
            c for c in value
            # which is not a numeric decoration (() is used for negative
            # by accountants)
            if c not in '()-+'
            # which is not a digit or a currency symbol
            if unicodedata.category(c) not in ('Nd', 'Sc')
        ]

        counts = collections.Counter(non_number)
        # if we have two non-numbers *and* the last one has a count of 1,
        # we probably have grouping & decimal separators
        if len(counts) == 2 and counts[non_number[-1]] == 1:
            return [character for character, _count in counts.most_common()]

        # otherwise get whatever's in the options, or fallback to a default
        thousand_separator = options.get('float_thousand_separator', ' ')
        decimal_separator = options.get('float_decimal_separator', '.')
        return thousand_separator, decimal_separator

    @api.model
    def _remove_currency_symbol(self, value):
        value = value.strip()
        negative = False
        # Careful that some countries use () for negative so replace it by - sign
        if value.startswith('(') and value.endswith(')'):
            value = value[1:-1]
            negative = True
        float_regex = re.compile(r'([+-]?[0-9.,]+)')
        split_value = [g for g in float_regex.split(value) if g]
        if len(split_value) > 2:
            # This is probably not a float
            return False
        if len(split_value) == 1:
            if float_regex.search(split_value[0]) is not None:
                return split_value[0] if not negative else '-' + split_value[0]
            return False
        else:
            # String has been split in 2, locate which index contains the float and which does not
            currency_index = 0
            if float_regex.search(split_value[0]) is not None:
                currency_index = 1
            # Check that currency exists
            currency = self.env['res.currency'].search([('symbol', '=', split_value[currency_index].strip())])
            if len(currency):
                return split_value[(currency_index + 1) % 2] if not negative else '-' + split_value[(currency_index + 1) % 2]
            # Otherwise it is not a float with a currency symbol
            return False

    def _import_image_by_url(self, url, session, field, line_number):
        """ Imports an image by URL

        :param str url: the original field value
        :param requests.Session session:
        :param str field: name of the field (for logging/debugging)
        :param int line_number: 0-indexed line number within the imported file (for logging/debugging)
        :return: the replacement value
        :rtype: bytes
        """
        maxsize = int(config.get("import_image_maxbytes", DEFAULT_IMAGE_MAXBYTES))
        _logger.debug("Trying to import image from URL: %s into field %s, at line %s" % (url, field, line_number))
        try:
            response = session.get(url, timeout=int(config.get("import_image_timeout", DEFAULT_IMAGE_TIMEOUT)))
            response.raise_for_status()

            if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > maxsize:
                raise ImportValidationError(
                    _("File size exceeds configured maximum (%s bytes)", maxsize),
                    field=field
                )

            content = bytearray()
            for chunk in response.iter_content(DEFAULT_IMAGE_CHUNK_SIZE):
                content += chunk
                if len(content) > maxsize:
                    raise ImportValidationError(
                        _("File size exceeds configured maximum (%s bytes)", maxsize),
                        field=field
                    )

            image = Image.open(io.BytesIO(content))
            w, h = image.size
            if w * h > 42e6:  # Nokia Lumia 1020 photo resolution
                raise ImportValidationError(
                    _("Image size excessive, imported images must be smaller than 42 million pixel"),
                    field=field
                )

            return base64.b64encode(content)
        except Exception as e:
            _logger.exception(e)
            raise ImportValidationError(
                _(
                    "Could not retrieve URL: %(url)s [%(field_name)s: L%(line_number)d]: %(error)s",
                    url=url, field_name=field, line_number=line_number + 1, error=e
                ),
                field=field
            )

    def _handle_multi_mapping(self, data, import_fields):
        """ This method handles multiple mapping on the same field.

        It will return the list of the mapped fields and the concatenated data for each field:

        - If two column are mapped on the same text or char field, they will end up
          in only one column, concatenated via space (char) or new line (text).
        - The same logic is used for many2many fields. Multiple values can be
          imported if they are separated by ``,``.

        Input/output Example:

        input data
            .. code-block:: python

                [
                    ["Value part 1", "1", "res.partner_id1", "Value part 2"],
                    ["I am", "1", "res.partner_id1", "Batman"],
                ]

        import_fields
            ``[desc, some_number, partner, desc]``

        output merged_data
            .. code-block:: python

                [
                    ["Value part 1 Value part 2", "1", "res.partner_id1"],
                    ["I am Batman", "1", "res.partner_id1"],
                ]
        fields
            ``[desc, some_number, partner]``
        """
        # Get fields and their occurrences indexes
        # Among the fields that have been mapped, we get their corresponding mapped column indexes
        # as multiple fields could have been mapped to multiple columns.
        mapped_field_indexes = {}
        for idx, field in enumerate(field for field in import_fields if field):
            mapped_field_indexes.setdefault(field, list()).append(idx)
        import_fields = list(mapped_field_indexes.keys())

        # recreate data and merge duplicates (applies only on text or char fields)
        # Also handles multi-mapping on "field of relation fields".
        merged_data = []
        for record in data:
            new_record = []
            for mapped_fields, indexes in mapped_field_indexes.items():
                split_fields = mapped_fields.split('/')
                target_field = split_fields[-1]

                # get target_field type (on target model)
                target_model = self.res_model
                for field in split_fields:
                    if field != target_field:  # if not on the last hierarchy level, retarget the model
                        target_model = self.env[target_model][field]._name
                field = self.env[target_model]._fields.get(target_field)
                field_type = field.type if field else ''

                # merge data if necessary
                if field_type == 'char':
                    new_record.append(' '.join(record[idx] for idx in indexes if record[idx]))
                elif field_type == 'text':
                    new_record.append('\n'.join(record[idx] for idx in indexes if record[idx]))
                elif field_type == 'many2many':
                    new_record.append(','.join(record[idx] for idx in indexes if record[idx]))
                else:
                    new_record.append(record[indexes[0]])

            merged_data.append(new_record)

        return merged_data, import_fields

    def _handle_fallback_values(self, import_field, input_file_data, fallback_values):
        """
        If there are fallback values, this method will replace the input file
        data value if it does not match the possible values for the given field.
        This is only valid for boolean and selection fields.

        .. note::

            We can consider that we need to retrieve the selection values for
            all the fields in fallback_values, as if they are present, it's because
            there was already a conflict during first import run and user had to
            select a fallback value for the field.

        :param: list import_field: ordered list of field that have been matched to import data
        :param: list input_file_data: ordered list of values (list) that need to be imported in the given import_fields
        :param: dict fallback_values:

            contains all the fields that have been tagged by the user to use a
            specific fallback value in case the value to import does not match
            values accepted by the field (selection or boolean) e.g.::

                {
                    'fieldName': {
                        'fallback_value': fallback_value,
                        'field_model': field_model,
                        'field_type': field_type
                    },
                    'state': {
                        'fallback_value': 'draft',
                        'field_model': field_model,
                        'field_type': 'selection'
                    },
                    'active': {
                        'fallback_value': 'true',
                        'field_model': field_model,
                        'field_type': 'boolean'
                    }
                }
        """
        # add possible selection values into our fallback dictionary for fields of type "selection"
        for field_string in fallback_values:
            if fallback_values[field_string]['field_type'] != "selection":
                continue
            field_path = field_string.split('/')
            target_field = field_path[-1]
            target_model = self.env[fallback_values[field_string]['field_model']]

            selection_values = [value.lower() for (key, value) in target_model.fields_get([target_field])[target_field]['selection']]
            fallback_values[field_string]['selection_values'] = selection_values

        # check fallback values
        for record_index, records in enumerate(input_file_data):
            for column_index, value in enumerate(records):
                field = import_field[column_index]

                if field in fallback_values:
                    fallback_value = fallback_values[field]['fallback_value']
                    # Boolean
                    if fallback_values[field]['field_type'] == "boolean":
                        value = value if value.lower() in ('0', '1', 'true', 'false') else fallback_value
                    # Selection
                    elif value.lower() not in fallback_values[field]["selection_values"]:
                        value = fallback_value if fallback_value != 'skip' else None  # don't set any value if we skip

                    input_file_data[record_index][column_index] = value

        return input_file_data

    def execute_import(self, input_data, input_columns, import_fields, options, dryrun=False):

        self.ensure_one()

        if not input_data:
            return {'messages': ['No input data!']}

        self._cr.execute('SAVEPOINT import')

        # Delete non-importable columns
        input_data, import_fields = self._map_import_data(input_data, import_fields, options)

        # Parse date and float field
        input_data = self._parse_import_data(input_data, import_fields, options)

        _logger.info('importing %d rows...', len(input_data))

        merged_data, import_fields = self._handle_multi_mapping(input_data, import_fields)

        if options.get('fallback_values'):
            merged_data = self._handle_fallback_values(import_fields, merged_data, options['fallback_values'])

        name_create_enabled_fields = options.pop('name_create_enabled_fields', {})
        import_limit = options.pop('limit', None)
        model = self.env[self.res_model].with_context(
            import_file=False,
            name_create_enabled_fields=name_create_enabled_fields,
            import_set_empty_fields=options.get('import_set_empty_fields', []),
            import_skip_records=options.get('import_skip_records', []),
            _import_limit=import_limit)
        import_result = model.load(import_fields, merged_data)
        _logger.info('done')

        # If transaction aborted, RELEASE SAVEPOINT is going to raise
        # an InternalError (ROLLBACK should work, maybe). Ignore that.
        # TODO: to handle multiple errors, create savepoint around
        #       write and release it in case of write error (after
        #       adding error to errors array) => can keep on trying to
        #       import stuff, and rollback at the end if there is any
        #       error in the results.
        try:
            if dryrun:
                self._cr.execute('ROLLBACK TO SAVEPOINT import')
                # cancel all changes done to the registry/ormcache
                self.pool.clear_caches()
                self.pool.reset_changes()
            else:
                self._cr.execute('RELEASE SAVEPOINT import')
        except psycopg2.InternalError:
            pass

        if 'name' in import_fields:
            index_of_name = import_fields.index('name')
            skipped = options.get('skip', 0)
            # pad front as data doesn't contain anythig for skipped lines
            r = import_result['name'] = [''] * skipped
            # only add names for the window being imported
            r.extend(x[index_of_name] for x in input_data[:import_limit])
            # pad back (though that's probably not useful)
            r.extend([''] * (len(input_data) - (import_limit or 0)))
        else:
            import_result['name'] = []

        skip = options.get('skip', 0)
        # convert load's internal nextrow to the imported file's
        if import_result['nextrow']: # don't update if nextrow = 0 (= no nextrow)
            import_result['nextrow'] += skip

        return import_result
