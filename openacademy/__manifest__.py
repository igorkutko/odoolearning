# -*- coding: utf-8 -*-
{
    'name': "openacademy",

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
    'category': 'OpenAcademy',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base',
                'board'],

    # always loaded
    'data': [
        'security/openacademy_groups.xml',
        'security/openacademy_course_security.xml',
        'security/ir.model.access.csv',
        'views/openacademy_course_views.xml',
        'views/openacademy_session_views.xml',
        'views/openacademy_session_templates.xml',
        'views/res_partner_views.xml',
        'report/openacademy_dashboards.xml',
        'views/openacademy_menus.xml',
        'wizard/openacademy_session_attendees_set_views.xml',
        'report/openacademy_session_reports.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'data/openacademy_course_demo.xml',
    ],
}
