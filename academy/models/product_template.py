# -*- coding: utf-8 -*-

from odoo import fields, models


class Courses(models.Model):
    # _name = 'academy.courses'
    _inherit = 'product.template'

    name = fields.Char('Name')
    teacher_id = fields.Many2one('academy.teacher', string='Teacher')
