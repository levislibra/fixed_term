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
	property_account_receivable_id = fields.Integer('Default debit id', compute='_compute_receivable')
	property_account_payable_id = fields.Integer('Default Credit id', compute='_compute_payable')
	amount_balance_account = fields.Float('Balance', compute='_compute_balance')
	amount = fields.Float('Monto', required=True)
	line_ids = fields.One2many('fixed.term.line', 'fixed_term_id', 'Lineas')
	interest_format = fields.Selection([('mensual', 'Mensual'), ('mensual_capitalizable', 'Mensual Capitalizable')], string='Formato del interes', required=True, default='mensual')
	periodic_count = fields.Integer('Cantidad de periodos', required=True)
	rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', required=True, default='periodo')
	rate_periodic = fields.Float('Tasa periodo', digits=(16,4))
	rate_per_day = fields.Float('Tasa por dia', digits=(16,6))
	state = fields.Selection([('borrador', 'Borrador'), ('activo', 'Activo'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')
	journal_id = fields.Many2one('account.journal', 'Diario de Plazo Fijo')
	init_account_move_id = fields.Many2one('account.move', 'Asiento inicial')
	finalized_account_move_id = fields.Many2one('account.move', 'Asiento de cierre')

	@api.one
	def _compute_receivable(self):
		self.property_account_receivable_id = self.partner_id.property_account_receivable_id.id

	@api.one
	def _compute_payable(self):
		self.property_account_payable_id = self.partner_id.property_account_payable_id.id

	@api.one
	def _compute_name(self):
		self.name = 'Plazo Fijo #' + str(self.id).zfill(6)

	@api.one
	@api.onchange('partner_id')
	def onchange_partner_id(self):
		self.account_id = False

	@api.one
	@api.onchange('account_id')
	def _compute_balance(self):
		balance = 0
		if self.account_id != False:
			for line_id in self.account_id.move_line_ids:
				if line_id.partner_id.id == self.partner_id.id:
					balance += line_id.balance
		self.amount_balance_account = balance * -1

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
		elif self.amount_balance_account <= 0:
			raise UserError("El balance de la cuenta seleccionada debe ser mayor a cero.")
		elif self.amount > self.amount_balance_account:
			raise UserError("El monto del Plazo Fijo debe ser menor o igual al balance de la cuenta.")
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

	@api.one
	def confirm_fixed_term(self):
		if len(self.line_ids) == 0:
			raise UserError("No puede confirmar un Plazo Fijo sin vencimientos.")
		elif self.amount <= 0:
			raise UserError("El monto del Plazo Fijo debe ser mayor a cero.")
		elif self.amount_balance_account <= 0:
			raise UserError("El balance de la cuenta seleccionada debe ser mayor a cero.")
		elif self.amount > self.amount_balance_account:
			raise UserError("El monto del Plazo Fijo debe ser menor o igual al balance de la cuenta.")			
		else:
			#Creamos asiento retirando el dinero de la cuenta del proveedor
			#y la acreditamos en la cuenta del diario seleccionado
			aml = {
			    'name': "Debito a Plazo Fijo",
			    'partner_id': self.partner_id.id,
			    'account_id': self.account_id.id,
			    'journal_id': self.journal_id.id,
			    'date': self.date,
			    'date_maturity': self.date,
			    'debit': self.amount,
			}

			aml2 = {
			    'name': "Credito por Plazo Fijo",
			    'account_id': self.journal_id.default_debit_account_id.id,
			    'journal_id': self.journal_id.id,
			    'date': self.date,
			    'date_maturity': self.date,
			    'credit': self.amount,
			    'partner_id': self.partner_id.id,
			}
			am_values = {
			    'journal_id': self.journal_id.id,
			    'partner_id': self.partner_id.id,
			    'state': 'draft',
			    'name': 'PLAZO-FIJO-GENERADO/'+str(self.id).zfill(5),
			    'date': self.date,
			    'line_ids': [(0, 0, aml), (0, 0, aml2)],
			}
			new_move_id = self.env['account.move'].create(am_values)
			new_move_id.post()
			self.init_account_move_id = new_move_id.id
			self.state = 'activo'
			for line_id in self.line_ids:
				line_id.state = 'activo'

	@api.multi
	def action_fixed_term_confirm(self):
		configuracion_id = self.env['fixed.term.config'].browse(1)
		if len(configuracion_id) > 0:
			default_journal_id = configuracion_id.journal_id
		params = {
			'fixed_term_id': self.id,
			'journal_id': default_journal_id.id,
		}
		view_id = self.env['fixed.term.confirm.wizard']
		new = view_id.create(params)
		return {
			'type': 'ir.actions.act_window',
			'name': 'Confirmar Plazo Fijo',
			'res_model': 'fixed.term.confirm.wizard',
			'view_type': 'form',
			'view_mode': 'form',
			'res_id'    : new.id,
			'view_id': self.env.ref('fixed_term.fixed_term_confirm_wizard_view', False).id,
			'target': 'new',
		}


class FixedTermLine(models.Model):
	_name = 'fixed.term.line'

	_order = 'date asc, id asc'
	name = fields.Char('Nombre', compute='_compute_name')
	date = fields.Date('Fecha')
	fixed_term_id = fields.Many2one('fixed.term', 'Plazo Fijo', ondelete='cascade')
	number = fields.Integer('Numero')
	amount = fields.Float('Monto')
	theoretical_amount = fields.Float('Monto teorico')
	date_maturity = fields.Date('Vencimiento')
	days = fields.Integer('Dias')
	rate_type = fields.Selection([('periodo', 'Periodo'), ('dia', 'Dia')], string='Interes por', select=True, default='periodo')
	rate_periodic = fields.Float('Tasa periodo', digits=(16,4))
	rate_per_day = fields.Float('Tasa por dia', digits=(16,6))
	interest_amount = fields.Float('Interes')
	state = fields.Selection([('borrador', 'Borrador'), ('activo', 'Activo'), ('por_facturar', 'A Facturar'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')
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
			self.interest_amount = round(self.amount * self.rate_periodic, 2)
		elif self.rate_type == 'dia':
			self.interest_amount = round(self.amount * self.days * self.rate_per_day, 2)

	@api.one
	def compute_line(self):
		# Compute days count
		self.compute_days()
		# Compute interest amount
		self.compute_interest_amount()

	@api.multi
	def action_confirm(self):    
		if True:
			params = {
				'fixed_term_line_id': self.id,
				'amount': self.amount,
				'date_maturity': self.date_maturity,
				'days': self.days,
				'rate_type': self.rate_type,
				'rate_periodic': self.rate_periodic,
				'rate_per_day': self.rate_per_day,
				'interest_amount': self.interest_amount,
			}
			view_id = self.env['fixed.term.line.wizard']
			new = view_id.create(params)
			return {
				'type': 'ir.actions.act_window',
				'name': 'Actualizar',
				'res_model': 'fixed.term.line.wizard',
				'view_type': 'form',
				'view_mode': 'form',
				'res_id'    : new.id,
				'view_id': self.env.ref('fixed_term.fixed_term_line_recalculate_wizard_view', False).id,
				'target': 'new',
			}


class FixedTermLine(models.Model):
	_name = 'fixed.term.config'

	name = fields.Char('Nombre', defualt='Configuracion general', readonly=True, required=True)
	journal_id = fields.Many2one('account.journal', 'Diario de Plazo Fijo')
