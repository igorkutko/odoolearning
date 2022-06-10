# -*- coding: utf-8 -*-

import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup

from odoo import fields, models


class ParserBitrix:

    def __init__(self):
        self.host = 'https://it-artel.bitrix24.ua/'
        self.url = self.host + 'company/'
        self.headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36 OPR/86.0.4363.59',
        }
        self.login = ''
        self.passwd = ''
        self.pages = 13
        self.request = None
        self.titles = []
        self.data = []
        self.content = []
        self.tags = {
            'title_row': ('th', 'main-grid-cell-head'),
            'title_cell': [
                ('div', 'main-grid-cell-inner'),
                ('span', 'main-grid-cell-head-container'),
                ('span', "main-grid-head-title"),
            ],
            'data_row': ('tr', 'main-grid-row'),
            'data_cell': ('td', 'main-grid-cell'),
            'data_content': [
                ('div', 'main-grid-cell-inner'),
                ('span', 'main-grid-cell-content'),
            ],
            'data_content_ref': [('a', '')],
            'data_content_img': [
                ('div', 'intranet-user-list-userpic'),
                ('i', ''),
            ],
        }

    @staticmethod
    def get_tags(parent, tags):
        element = None
        if not parent:
            return element
        for tag, attr_value in tags:
            element = parent.find(tag, class_=attr_value) if attr_value else parent.find(tag)
            if element is None:
                break
            else:
                parent = element
        return element

    @staticmethod
    def get_img_content(img):
        img_content = ''
        img_attr = 'style'
        img_style = 'background-image:'
        if img.attrs.get(img_attr):
            img_urls = [kv[len(img_style):] for kv in img.attrs.get(img_attr).split(';') if
                        kv.startswith(img_style)]
            img_url = img_urls[0].strip()
            img_content = img_url[len('url(\''):-len('\')')]
        return img_content

    @staticmethod
    def convert_value(title, value):
        months = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня',
                  'липня', 'серпня', 'вересня', 'жовтня', 'листопада', 'грудня']
        y = 2000
        genders_ua = ['чоловіча', 'жіноча']
        genders_en = ['Male', 'Female', 'Other']

        is_modified = False
        if title == 'Дата народження':
            d = None
            m = None
            parts = value.split(' ')
            if len(parts) == 2:
                d = int(parts[0])
                month = parts[1]
                m = months.index(month) + 1 if month in months else None
            if d and m:
                value = '{:0>2d}-{:0>2d}-{:0>4d}'.format(d, m, y)
                is_modified = True
        elif title.startswith('Дата'):
            parts = value.split(' ')
            date_only = parts[0] if len(parts) > 0 else None
            value = date_only.replace('.', '-') if date_only else ''
            is_modified = True
        elif title.startswith('Стать'):
            value = genders_en[genders_ua.index(value)] if value in genders_ua else genders_en[2]
            is_modified = True

        return is_modified, value

    def get_titles(self, bs):
        row_tag = self.tags['title_row']
        cell_tags = self.tags['title_cell']

        tag, attr_value = row_tag
        cell_heads = bs.find_all(tag, class_=attr_value)
        for cell_head in cell_heads:
            elem = ParserBitrix.get_tags(cell_head, cell_tags)
            head_title = elem.get_text() if elem is not None else ''
            self.titles.append(head_title)
        # print(self.titles)

    def get_data(self, bs):
        result = False

        row_tag = self.tags['data_row']
        cell_tag = self.tags['data_cell']
        content_tags = self.tags['data_content']
        content_ref_tags = self.tags['data_content_ref']
        content_img_tags = self.tags['data_content_img']

        tag, attr_value = row_tag
        items = bs.find_all(tag, class_=attr_value)
        for item in items:
            values = []
            tag, attr_value = cell_tag
            cells = item.find_all(tag, class_=attr_value)
            for cell in cells:
                elem = ParserBitrix.get_tags(cell, content_tags)
                ref = ParserBitrix.get_tags(elem, content_ref_tags)
                img = ParserBitrix.get_tags(elem, content_img_tags)
                if img:
                    value = ParserBitrix.get_img_content(img)
                elif ref:
                    value = ref.get_text(strip=True)
                elif elem:
                    value = elem.get_text(strip=True)
                else:
                    value = ''
                values.append(value)
            fields_values = [value for value in values if value]
            if fields_values:
                self.data.append(values)
                result = True
            else:
                continue
            # print(values)

            content_item = {}
            for i in range(0, len(self.titles)):
                title = self.titles[i]
                value = values[i]
                is_modified, value = ParserBitrix.convert_value(title, value)
                if is_modified:
                    values[i] = value
                content_item[title] = value

            self.content.append(content_item)

        return result

    def get_page(self, params=None):
        self.request = requests.get(self.url,
                                    headers=self.headers,
                                    params=params,
                                    auth=HTTPBasicAuth(self.login, self.passwd))

    def get_content(self):
        bs = BeautifulSoup(self.request.text, 'html.parser')

        if not self.titles:
            self.get_titles(bs)

        result = self.get_data(bs)
        return result

    def do_parse(self):

        self.titles = []
        self.data = []
        self.content = []

        page = 1

        self.get_page()
        while self.request.status_code == 200:
            if not self.get_content():
                break
            page += 1
            if page > self.pages:
                break
            self.get_page(params={'page': f'page-{page}'})


class BitrixImport(models.TransientModel):
    _name = 'ata_parser.bitrix_import'
    _description = 'Import data from Bitrix'

    url = fields.Char('URL')
    login = fields.Char('Login')
    password = fields.Char('Password')

    def import_data(self):
        parser_bitrix = ParserBitrix()
        # parser_bitrix.url = self.url
        parser_bitrix.login = self.login
        parser_bitrix.passwd = self.password
        parser_bitrix.do_parse()
        return parser_bitrix

    def update_record(self, identity_field, values):
        dm = self.env['hr.employee']
        identity_value = values[identity_field]
        record = dm.search([(identity_field, '=', identity_value)], limit=1)
        if not record:  # create new record
            dm.create(values)
        else:  # update current record
            record.write(values)

    def save_data(self, parser_obj, dryrun=False):
        rules = [
            ("", ""),
            ("Фото", "image_1920"),
            ("Ім'я та прізвище", "name"),
            ("Ім'я", ""),
            ("Прізвище", ""),
            ("По батькові", ""),
            ("E-Mail", "work_email"),
            ("Дата реєстрації", "departure_date"),
            ("Дата народження", "birthday"),
            ("Стать", "gender"),
            ("Мобільний телефон", "mobile_phone"),
            ("Місто", "additional_note"),
            ("Робочий телефон", "work_phone"),
            ("Посада", "job_id"),
            ("Підрозділ", "department_id"),
            ("Внутрішній телефон", ""),
            ("ІПН", ""),
            ("Skype", "notes"),
            ("Дата прийняття на роботу", "work_permit_expiration_date"),
            ("", ""),
        ]

        # identity_field = "name"

        data_fields = [f for t, f in rules]
        options = {'skip': 0,
                   'limit': None,
                   'date_format': '%d-%m-%Y',
                   'datetime_format': '%d-%m-%Y %H:%M:%S',
                   'float_thousand_separator': ' ',
                   'float_decimal_separator': '.',
                   'fallback_values': {},
                   'name_create_enabled_fields': {'job_id': True, 'department_id': True},
                   'import_set_empty_fields': [],
                   'import_skip_records': [],
                   'has_headers': False
                   }

        import_record = self.env['ata_parser.data_import'].create({
            'res_model': 'hr.employee',
        })

        import_result = import_record.execute_import(
            parser_obj.data,
            parser_obj.titles,
            data_fields,
            options,
            dryrun
        )

        # print(import_result)

        return import_result

    def import_employees(self):
        parser_object = self.import_data()
        import_result = self.save_data(parser_object)
        is_ok = True if import_result['ids'] else False
        user_message = 'Test successfully done!' if is_ok else '\n'.join(import_result['messages'])
        message = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Warning!',
                'message': user_message,
                'sticky': True
            }
         }
        return message

    def test_import_employees(self):
        parser_object = self.import_data()
        import_result = self.save_data(parser_object, True)
        is_ok = True if import_result['ids'] else False
        user_message = 'Test successfully done!' if is_ok else '\n'.join(import_result['messages'])
        # 'fadeout': 'slow'|'fast'|'no'
        message_effect = {
            'effect': {
                'fadeout': 'slow',
                'message': user_message,
                'type': 'rainbow_man',
            }
        }
        message = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Warning!',
                'message': user_message,
                'sticky': True
            }
         }
        return message
