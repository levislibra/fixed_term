# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time

class FixedTermLineWizard(models.TransientModel):
    _name = 'fixed.term.line.wizard'

    fixed_term_line_id = fields.Many2one('fixed.term.line', string='Line')
    amount = fields.Float('Monto')
    date = fields.Date('Fecha')
    date_maturity = fields.Date('Fecha hasta')
    precancelable = fields.Boolean('Precancelable', readonly=True)
    execute_precancelable = fields.Boolean('Pre-cancelar Plazo Fijo?', default=False)
    new_date_maturity = fields.Date('Nueva Fecha')
    days = fields.Integer('Dias')
    rate_periodic = fields.Float('Tasa del periodo', digits=(16,4))
    precancelable_rate_periodic = fields.Float('Tasa del periodo cancelado', digits=(16,6))
    precancelable_rate_periodic_aplicate = fields.Float('Tasa aplicada', digits=(16,6), readonly=True)
    interest_amount = fields.Float('Interes')

    @api.one
    def recalculate_fixed_term_line(self):
        if self.execute_precancelable:
            if self.new_date_maturity <= self.date or self.new_date_maturity >= self.date_maturity:
                raise ValidationError('La nueva fecha debe ser mayor a la fecha de inicio y menor a la fecha de vencimiento.')
        fixed_term_line_id = self.fixed_term_line_id
        fixed_term_line_id.amount = self.amount
        fixed_term_line_id.date_maturity = self.new_date_maturity
        fixed_term_line_id.rate_periodic = self.rate_periodic
        fixed_term_line_id.precancelable_rate_periodic = self.precancelable_rate_periodic
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
 
class FixedTermLineValidateWizard(models.TransientModel):
    _name = 'fixed.term.line.validate.wizard'

    fixed_term_line_id = fields.Many2one('fixed.term.line', string='Plazo Fijo')
    invoice_journal_id = fields.Many2one('account.journal', string='Diario de factura')
    use_documents = fields.Boolean('Usa Documento', related='invoice_journal_id.use_documents', readonly=True)
    document_number = fields.Char('Numero de documento')

    @api.one
    def validate_fixed_term_line(self):
        fixed_term_line_id = self.fixed_term_line_id
        fixed_term_line_id.journal_id = self.invoice_journal_id
        fixed_term_line_id.document_number = self.document_number
        fixed_term_line_id.validate_fixed_term_line()