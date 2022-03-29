# -*- coding: utf-8 -*-
from odoo import http


class Academy(http.Controller):

    @http.route('/academy/academy', auth='public', website=True)
    def index(self, **kw):
        teachers = http.request.env['academy.teachers']
        index_page = http.request.render('academy.index', {
            'teachers': teachers.search([]),
        })
        return index_page

    @http.route('/academy/<name>/', auth='public', website=True)
    def teacher_name(self, name):
        teacher_page = '<h1>{}</h1>'.format(name)
        return teacher_page

    @http.route('/academy_tid/<int:tid>/', auth='public', website=True)
    def teacher_id(self, tid):
        teacher_page = '<h1>{} ({})</h1>'.format(tid, type(tid).__name__)
        return teacher_page

    @http.route('/academy/<model("academy.teachers"):teacher>/', auth='public', website=True)
    def teacher(self, teacher):
        teacher_page = http.request.render('academy.biography', {
            'person': teacher
        })
        return teacher_page

#     @http.route('/academy/academy/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('academy.listing', {
#             'root': '/academy/academy',
#             'objects': http.request.env['academy.academy'].search([]),
#         })

#     @http.route('/academy/academy/objects/<model("academy.academy"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('academy.object', {
#             'object': obj
#         })
