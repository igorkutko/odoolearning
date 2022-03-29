# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Teachers(models.Model):
    _name = 'academy.teachers'

    name = fields.Char(string='Title')
    biography = fields.Html()
    courses_ids = fields.One2many('product.template', 'teacher_id', string="Courses")


class Courses(models.Model):
    # _name = 'academy.courses'
    _inherit = 'product.template'

    name = fields.Char('Name')
    teacher_id = fields.Many2one('academy.teachers', string='Teacher')
