# -*- coding: utf-8 -*-

from odoo import fields, models


class Teachers(models.Model):
    _name = 'academy.teacher'
    _description = 'Teachers'

    name = fields.Char(string='Title')
    biography = fields.Html()
    courses_ids = fields.One2many('product.template', 'teacher_id', string="Courses")
