# -*- coding: utf-8 -*-
{
    'name': "Academy",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Academy',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base',
                'mail',
                'website_sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/product_public_category_data.xml',
        'views/academy_teacher_views.xml',
        'views/product_template_views.xml',
        'views/academy_templates.xml',
        'views/academy_menus.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'data/academy_teacher_demo.xml',
        'data/product_template_demo.xml',
    ],
}
