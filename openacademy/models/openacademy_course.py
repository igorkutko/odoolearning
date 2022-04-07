# -*- coding: utf-8 -*-

from odoo import fields, models


class Course(models.Model):
    _name = 'openacademy.course'
    _description = 'Course'

    name = fields.Char(string='Title')
    description = fields.Text()
    responsible_id = fields.Many2one('res.users', string='Responsible')
    session_ids = fields.One2many('openacademy.session', 'course_id', string='Sessions')

    _sql_constraints = [('description_not_title',
                         'CHECK(description != name)',
                         'Course description and the course title are not different'),
                        ('title_unique',
                         'UNIQUE(name)',
                         'Course’s name not UNIQUE')]

    def copy(self, default=None):
        default = default if type(default) is dict else {}
        cnt = self.env['openacademy.course'].search_count([
            ('name', '=like', 'Copy of {}%'.format(self.name))])
        cntstr = ' ({})'.format(cnt) if cnt else ''
        default['name'] = 'Copy of {}{}'.format(self.name, cntstr)
        return super(Course, self).copy(default)
