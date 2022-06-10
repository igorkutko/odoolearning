# -*- coding: utf-8 -*-
{
    'name': "Parser (Bitrix)",

    'summary': """
        Import data from Bitrix to Odoo""",

    'description': """
        Import data from Bitrix (company) to Odoo (employee)
    """,

    'author': "IT Artel",
    'website': "http://www.it-artel.ua",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Wizard.Parser',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base',
                'hr'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'wizard/parser_bitrix_import_views.xml',
        'views/parser_bitrix_import_menu.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}
