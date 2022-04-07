# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Session(models.Model):
    _name = 'openacademy.session'
    _description = 'Session'

    name = fields.Char(string='Title')
    active = fields.Boolean(default=True)
    start_date = fields.Date(string='Start date', default=lambda self: fields.Date.today())
    duration = fields.Integer(string='Duration')
    number_of_seats = fields.Integer(string='Number of seats')
    taken_seats = fields.Float(compute='_compute_taken_seats')
    instructor_id = fields.Many2one('res.partner',
                                    string='Instructor',
                                    domain=['|', ('instructor', '=', True),
                                            ('category_id.name', 'ilike', 'Teacher')])
    course_id = fields.Many2one('openacademy.course', string='Course')
    attendees_ids = fields.Many2many('res.partner', string='Attendees')
    attendees_count = fields.Integer(string='Count of attendees', compute='_compute_attendees_count', store=True)

    @api.depends('number_of_seats', 'attendees_ids')
    def _compute_taken_seats(self):
        for line in self:
            line.taken_seats = (len(line.attendees_ids) / line.number_of_seats) * 100 if line.number_of_seats else 0

    @api.depends('attendees_ids')
    def _compute_attendees_count(self):
        for line in self:
            line.attendees_count = len(line.attendees_ids)

    @api.onchange('number_of_seats')
    def _onchange_number_of_seats(self):
        result = {}
        if self.number_of_seats < 0:
            result = {'warning': {
                'title': 'Invalid values: negative number of seats',
                'message': 'Invalid values: negative number of seats. Correct!',
                'type': 'warning'
            }}
        return result

    @api.onchange('number_of_seats', 'attendees_ids')
    def _onchange_check_seats(self):
        result = {}
        if self.number_of_seats < len(self.attendees_ids):
            result = {'warning': {
                'title': 'Invalid values: more participants than seats.',
                'message': 'Invalid values: more participants than seats. Correct!',
                'type': 'warning'
            }}
        return result

    @api.constrains('instructor_id', 'attendees_ids')
    def _constraints_instructor(self):
        for line in self:
            if line.instructor_id in line.attendees_ids:
                raise ValidationError('Instructor is present in the attendees of his/her own session!')
