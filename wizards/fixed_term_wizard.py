# -*- coding: utf-8 -*-

from openerp import models, fields, api

class FixedTermLineWizard(models.TransientModel):
    _name = 'fixed.term.line.wizard'

    def _get_default_line(self):
        return self.env['fixed.term.line'].browse(self.env.context.get('active_id'))

    def _get_default_amount(self):
        return self.fixed_term_line_id.amount

    def _get_default_date_maturity(self):
        return self.fixed_term_line_id.date_maturity

    def _get_default_days(self):
        return self.fixed_term_line_id.days

    def _get_default_rate_type(self):
        return self.fixed_term_line_id.rate_type

    def _get_default_rate_periodic(self):
        return self.fixed_term_line_id.rate_periodic

    def _get_default_rate_per_day(self):
        return self.fixed_term_line_id.rate_per_day

    def _get_default_interest_amount(self):
        return self.fixed_term_line_id.interest_amount

    fixed_term_line_id = fields.Many2one('fixed.term.line', string='Line', default=_get_default_line)
    amount = fields.Float('Monto', default=_get_default_amount)
    date_maturity = fields.Date('Fecha hasta', default=_get_default_date_maturity)
    days = fields.Integer('Dias', default=_get_default_days)
    rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', select=True, default=_get_default_rate_type)
    rate_periodic = fields.Float('Tasa periodo', default=_get_default_rate_periodic)
    rate_per_day = fields.Float('Tasa por dia', digits=(16,6), default=_get_default_rate_per_day)
    interest_amount = fields.Float('Interes', default=_get_default_interest_amount)

