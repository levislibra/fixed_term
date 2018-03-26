# -*- coding: utf-8 -*-

from openerp import models, fields, api

class FixedTermLineWizard(models.TransientModel):
    _name = 'fixed.term.line.wizard'

    fixed_term_line_id = fields.Many2one('fixed.term.line', string='Line')
    amount = fields.Float('Monto')
    date_maturity = fields.Date('Fecha hasta')
    days = fields.Integer('Dias')
    rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', select=True)
    rate_periodic = fields.Float('Tasa periodo', digits=(16,4))
    rate_per_day = fields.Float('Tasa por dia', digits=(16,6))
    interest_amount = fields.Float('Interes')

    @api.one
    def recalculate_fixed_term_line(self):
        fixed_term_line_id = self.fixed_term_line_id

        fixed_term_line_id.amount = self.amount
        fixed_term_line_id.date_maturity = self.date_maturity
        #fixed_term_line_id.days = self.days
        fixed_term_line_id.rate_type = self.rate_type
        fixed_term_line_id.rate_periodic = self.rate_periodic
        fixed_term_line_id.rate_per_day = self.rate_per_day
        #fixed_term_line_id.interest_amount = self.interest_amount
        fixed_term_line_id.compute_line()

class FixedTermConfirmWizard(models.TransientModel):
    _name = 'fixed.term.confirm.wizard'

    fixed_term_id = fields.Many2one('fixed.term', string='Plazo Fijo')
    journal_id = fields.Many2one('account.journal', string='Diario de Plazo Fijo')

    @api.one
    def confirm_fixed_term(self):
        fixed_term_id = self.fixed_term_id
        fixed_term_id.journal_id = self.journal_id
        fixed_term_id.confirm_fixed_term()
 