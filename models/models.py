# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time
import numpy as np

class FixedTerm(models.Model):
	_name = 'fixed.term'

	name = fields.Char('Nombre', compute='_compute_name')
	date = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
	partner_id = fields.Many2one('res.partner', 'Proveedor', required=True)
	account_id = fields.Many2one('account.account', 'Cuenta', required=True)
	amount_balance_account = fields.Float('Balance', readonly=True)
	amount = fields.Float('Monto', required=True)
	line_ids = fields.One2many('fixed.term.line', 'fixed_term_id', 'Lineas')
	interest_format = fields.Selection([('mensual', 'Mensual'), ('mensual_capitalizable', 'Mensual Capitalizable')], string='Formato del interes', required=True, default='mensual')
	periodic_count = fields.Integer('Cantidad de periodos', required=True)
	rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', required=True, default='periodo')
	rate_periodic = fields.Float('Tasa periodo')
	rate_per_day = fields.Float('Tasa por dia')
	state = fields.Selection([('borrador', 'Borrador'), ('activo', 'Activo'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')

	@api.one
	def _compute_name(self):
		self.name = 'Plazo Fijo #' + str(self.id).zfill(6)

	def delete_lines(self):
		if self.state == 'borrador':
			for line_id in self.line_ids:
				line_id.unlink()
		else:
			raise UserError("Solo puede borrar lineas de un Plazo Fijo en borrador.")

	@api.one
	def compute_lines(self):
		if self.amount <= 0:
			raise UserError("El monto del Plazo Fijo debe ser mayor a cero.")
		else:
			self.delete_lines()
			initial_date = datetime.strptime(self.date, "%Y-%m-%d")
			amount = self.amount
			new_line_id = None
			old_line_id = None
			prev_fixed_term_line_id = None
			date_maturity = None
			i = 1
			while i <= self.periodic_count:
				relative_date = relativedelta.relativedelta(months=i)
				if new_line_id != None:
					prev_fixed_term_line_id = new_line_id.id
					old_line_id = new_line_id
				date_maturity = datetime.strptime(self.date, "%Y-%m-%d") + relative_date
				new_line = {
						'fixed_term_id': self.id,
						'date': initial_date,
						'number': i,
						'amount': amount,
						#'theoretical_amount': algo,
						'date_maturity': date_maturity,
						'rate_type': self.rate_type,
						'rate_periodic': self.rate_periodic,
						'rate_per_day': self.rate_per_day,
						'state': 'borrador',
						'prev_fixed_term_line_id': prev_fixed_term_line_id,
				}
				new_line_id = self.env['fixed.term.line'].create(new_line)
				new_line_id.compute_line()
				if old_line_id != None:
					old_line_id.next_fixed_term_line_id = new_line_id.id
				self.line_ids = [new_line_id.id]
				i += 1
				initial_date = date_maturity
				if self.interest_format == 'mensual_capitalizable':
					amount = new_line_id.amount + new_line_id.interest_amount

class FixedTermLine(models.Model):
	_name = 'fixed.term.line'

	name = fields.Char('Nombre', compute='_compute_name')
	date = fields.Date('Fecha')
	fixed_term_id = fields.Many2one('fixed.term', 'Plazo Fijo', ondelete='cascade')
	number = fields.Integer('Numero')
	amount = fields.Float('Monto')
	theoretical_amount = fields.Float('Monto teorico')
	date_maturity = fields.Date('Vencimiento')
	days = fields.Integer('Dias')
	rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', select=True, default='periodo')
	rate_periodic = fields.Float('Tasa periodo')
	rate_per_day = fields.Float('Tasa por dia')
	interest_amount = fields.Float('Interes')
	state = fields.Selection([('borrador', 'Borrador'), ('activo', 'Activo'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')
	prev_fixed_term_line_id = fields.Many2one('fixed.term.line', 'Linea previa')
	next_fixed_term_line_id = fields.Many2one('fixed.term.line', 'Linea proxima')
	invoice_id = fields.Many2one('account.invoice', 'Factura')

	@api.one
	def _compute_name(self):
		self.name = 'Vencimiento #' + str(self.number).zfill(6)

	@api.one
	def compute_days(self):
		date = datetime.strptime(str(self.date), "%Y-%m-%d")
		date_maturity = datetime.strptime(self.date_maturity, "%Y-%m-%d")
		if date_maturity > date:
			count_days = date_maturity - date
			self.days = count_days.days
		else:
			self.days = 0

	@api.one
	def compute_interest_amount(self):
		if self.rate_type == 'periodo':
			self.interest_amount = self.amount * self.rate_periodic
		elif self.rate_type == 'dia':
			self.interest_amount = self.amount * self.days * self.rate_per_day

	@api.one
	def compute_line(self):
		# Compute days count
		self.compute_days()
		# Compute interest amount
		self.compute_interest_amount()
		

