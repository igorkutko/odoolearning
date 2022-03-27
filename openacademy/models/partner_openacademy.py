from odoo import models, fields


class PartnerOpenAcademy(models.Model):
    _inherit = 'res.partner'

    instructor = fields.Boolean(string='Is instructor')
    session_ids = fields.Many2many('openacademy.session', string='Sessions')
