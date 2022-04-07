# -*- coding: utf-8 -*-

from odoo import fields, models


class SessionAttendeesSet(models.TransientModel):
    _name = 'openacademy.session_attendees_set'
    _description = 'Set attendees for sessions'

    def _default_session_ids(self):
        session_manager = self.env['openacademy.session']
        active_ids = self._context.get('active_ids')
        default_session_ids = session_manager.browse(active_ids)
        return default_session_ids

    session_ids = fields.Many2many('openacademy.session', string='Session', default=_default_session_ids)
    attendees_ids = fields.Many2many('res.partner')

    def set_session_attendees(self):
        for record in self:
            for session_id in record.session_ids:
                session_id.attendees_ids = record.attendees_ids
        return {}
