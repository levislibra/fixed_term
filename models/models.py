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
	property_account_receivable_id = fields.Integer('Default debit id', copute='_compute_receivable')
	property_account_payable_id = fields.Integer('Default Credit id', compute='_compute_payable')
	amount_balance_account = fields.Float('Balance', compute='_compute_balance')
	currency_id = fields.Many2one('res.currency', string="Moneda")
	amount = fields.Float('Monto', required=True)
	vat_tax = fields.Boolean('IVA', default=False)
	vat_tax_included = fields.Boolean('IVA incluido', default=False)
	vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', domain="[('type_tax_use', '=', 'purchase')]")
	line_ids = fields.One2many('fixed.term.line', 'fixed_term_id', 'Lineas')
	unit_of_time = fields.Selection([('mensual', 'Mensual'), ('bimestral', 'Bimestral'), ('trimestral', 'Trimestral'), ('cuatrimestral', 'Cuatrimestral'), ('semestral', 'Semestral'), ('anual', 'Anual')], string='Unidad de tiempo', required=True, default='mensual')
	periodic_time = fields.Integer('Cantidad de periodos', required=True)
	compound_interest = fields.Boolean('Interes compuesto', default=False)
	rate_periodic = fields.Float('Tasa del periodo', digits=(16,6))
	precancelable = fields.Boolean('Precancelable', default=True)
	precancelable_rate_periodic = fields.Float('Tasa del periodo cancelado', digits=(16,6))
	state = fields.Selection([('borrador', 'Borrador'), ('activo', 'Activo'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')
	journal_id = fields.Many2one('account.journal', 'Diario de Plazo Fijo')
	init_account_move_id = fields.Many2one('account.move', 'Asiento inicial')
	finalized_account_move_id = fields.Many2one('account.move', 'Asiento de cierre')

	@api.one
	@api.onchange('partner_id')
	def _compute_receivable(self):
		self.property_account_receivable_id = self.partner_id.property_account_receivable_id.id

	@api.one
	@api.onchange('partner_id')
	def _compute_payable(self):
		self.property_account_payable_id = self.partner_id.property_account_payable_id.id

	@api.one
	@api.onchange('partner_id', 'account_id')
	def _compute_currency_id(self):
		if len(self.account_id.currency_id) > 0:
			self.currency_id = self.account_id.currency_id
		else:
			self.currency_id = self.env.user.company_id.currency_id.id

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
			while i <= self.periodic_time:
				if self.unit_of_time == "mensual":
					relative_date = relativedelta.relativedelta(months=i)
				if self.unit_of_time == "bimestral":
					relative_date = relativedelta.relativedelta(months=i*2)
				elif self.unit_of_time == "trimestral":
					relative_date = relativedelta.relativedelta(months=i*3)
				elif self.unit_of_time == "cuatrimestral":
					relative_date = relativedelta.relativedelta(months=i*4)
				elif self.unit_of_time == "semestral":
					relative_date = relativedelta.relativedelta(months=i*6)
				elif self.unit_of_time == "anual":
					relative_date = relativedelta.relativedelta(years=i)
				
				if new_line_id != None:
					prev_fixed_term_line_id = new_line_id.id
					old_line_id = new_line_id
				date_maturity = datetime.strptime(self.date, "%Y-%m-%d") + relative_date
				new_line = {
						'fixed_term_id': self.id,
						'date': initial_date,
						'date_maturity': date_maturity,
						'number': i,
						'amount': amount,
						'vat_tax': self.vat_tax,
						'vat_tax_included': self.vat_tax_included,
						'vat_tax_id': self.vat_tax_id.id,
						'rate_periodic': self.rate_periodic,
						'precancelable_rate_periodic': self.precancelable_rate_periodic,
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
				if self.compound_interest:
					# Interes capitalizable
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
			i = 0
			for line_id in self.line_ids:
				if i == 0:
					line_id.state = 'activo'
				else:
					line_id.state = 'pendiente'
				i += 1

	@api.multi
	def action_fixed_term_confirm(self):
		configuracion_id = self.env['fixed.term.config'].browse(1)
		default_journal_id = None
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
			'view_id': self.env.ref('fixed_term.fixed_term_confirm_wizard', False).id,
			'target': 'new',
		}


class FixedTermLine(models.Model):
	_name = 'fixed.term.line'

	_order = 'date asc, id asc'
	name = fields.Char('Nombre', compute='_compute_name')
	date = fields.Date('Fecha')
	fixed_term_id = fields.Many2one('fixed.term', 'Plazo Fijo', ondelete='cascade')
	partner_id = fields.Many2one('res.partner', 'Proveedor', related='fixed_term_id.partner_id', readonly=True)
	number = fields.Integer('Numero')
	amount = fields.Float('Monto')
	vat_tax = fields.Boolean('IVA', default=False)
	vat_tax_included = fields.Boolean('IVA incluido', default=False)
	vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', domain="[('type_tax_use', '=', 'purchase')]")
	vat_tax_amount = fields.Float('Monto IVA')
	total_amount = fields.Float('Total')
	date_maturity = fields.Date('Vencimiento')
	days = fields.Integer('Dias')
	percentage_complete_of_time = fields.Float("Completado", readonly=True, default=1)
	journal_id = fields.Many2one('account.journal', 'Diario')

	unit_of_time = fields.Selection([('mensual', 'Mensual'), ('bimestral', 'Bimestral'), ('trimestral', 'Trimestral'), ('cuatrimestral', 'Cuatrimestral'), ('semestral', 'Semestral'), ('anual', 'Anual')], string='Unidad de tiempo', related='fixed_term_id.unit_of_time', readonly=True)
	compound_interest = fields.Boolean('Interes compuesto', related='fixed_term_id.compound_interest', readonly=True)
	precancelable = fields.Boolean('Precancelable', related='fixed_term_id.precancelable', readonly=True)
	periodic_time = fields.Integer('Cantidad de periodos', related='fixed_term_id.periodic_time', readonly=True)
	rate_periodic = fields.Float('Tasa periodo', digits=(16,6))
	precancelable_rate_periodic = fields.Float('Tasa periodo cancelado', digits=(16,6))

	currency_id = fields.Many2one('res.currency', string="Moneda", related='fixed_term_id.currency_id', readonly=True)
	interest_amount = fields.Float('Interes')
	state = fields.Selection([('borrador', 'Borrador'), ('pendiente', 'Pendiente'), ('activo', 'Activo'), ('por_facturar', 'A Facturar'), ('precancelado', 'Precancelado'), ('finalizado', 'Finalizado'), ('cancelado', 'Cancelado')], string='Estado', readonly=True, default='borrador')
	sub_state = fields.Selection([('activo', 'Activo'), ('por_facturar', 'A Facturar'), ('precancelado', 'Precancelado')], string='Sub estado', readonly=True, default='activo')
	prev_fixed_term_line_id = fields.Many2one('fixed.term.line', 'Linea previa')
	next_fixed_term_line_id = fields.Many2one('fixed.term.line', 'Linea proxima')
	invoice_id = fields.Many2one('account.invoice', 'Factura')
	document_number = fields.Char('Numero de documento')

	@api.one
	def _compute_name(self):
		self.name = 'Vencimiento #' + str(self.number).zfill(6)

	@api.one
	def compute_days(self):
		old_days = self.days
		date = datetime.strptime(str(self.date), "%Y-%m-%d")
		date_maturity = datetime.strptime(self.date_maturity, "%Y-%m-%d")
		if date_maturity > date:
			count_days = date_maturity - date
			self.days = count_days.days
		else:
			self.days = 0

		if old_days == 0:
			self.percentage_complete_of_time = 1
		else:
			self.percentage_complete_of_time = (self.days * self.percentage_complete_of_time) / old_days

	@api.one
	def compute_interest_amount(self):
		self.interest_amount = round(self.amount * self.rate_periodic, 2)
		if self.vat_tax and self.vat_tax_included:
			self.interest_amount = round(self.interest_amount / (1 + self.vat_tax_id.amount / 100), 2)


	@api.one
	def compute_vat_tax_amount(self):
		if self.vat_tax:
			self.vat_tax_amount = round(self.interest_amount * round(self.vat_tax_id.amount/100, 2), 2)
		else:
			self.vat_tax_amount = 0

	@api.one
	def compute_total_amount(self):
		self.total_amount = self.interest_amount + self.vat_tax_amount

	@api.one
	def compute_line(self):
		# Compute days count
		self.compute_days()
		# Compute interest amount
		self.compute_interest_amount()
		# compute tax
		self.compute_vat_tax_amount()
		# compute total
		self.compute_total_amount()

	@api.multi
	def action_confirm(self):
		params = {
			'fixed_term_line_id': self.id,
			'date': self.date,
			'amount': self.amount,
			'date_maturity': self.date_maturity,
			'new_date_maturity': self.date_maturity,
			'days': self.days,
			'rate_periodic': self.rate_periodic,
			'precancelable_rate_periodic': self.precancelable_rate_periodic,
			'interest_amount': self.interest_amount,
			'precancelable': self.precancelable,
		}
		view_id = self.env['fixed.term.line.wizard']
		new = view_id.create(params)
		return {
			'type': 'ir.actions.act_window',
			'name': 'Actualizar',
			'res_model': 'fixed.term.line.wizard',
			'view_type': 'form',
			'view_mode': 'form',
			'res_id': new.id,
			'view_id': self.env.ref('fixed_term.fixed_term_line_recalculate_wizard', False).id,
			'target': 'new',
		}

	@api.multi
	def action_validate(self):
		configuracion_id = self.env['fixed.term.config'].browse(1)
		default_journal_id = None
		if len(configuracion_id) > 0:
			invoice_journal_id = configuracion_id.invoice_journal_id
		params = {
			'fixed_term_line_id': self.id,
			'invoice_journal_id': invoice_journal_id.id,
		}
		view_id = self.env['fixed.term.line.validate.wizard']
		new = view_id.create(params)
		return {
			'type': 'ir.actions.act_window',
			'name': 'Validar',
			'res_model': 'fixed.term.line.validate.wizard',
			'view_type': 'form',
			'view_mode': 'form',
			'res_id': new.id,
			'view_id': self.env.ref('fixed_term.fixed_term_validate_wizard', False).id,
			'target': 'new',
		}

	@api.one
	def action_cancel(self):
		print "CANCELLLLLLLLLL"
		if self.compound_interest:
			if self.prev_fixed_term_line_id.state == 'finalizado':
				self.generate_invoice()
		self.state = 'cancelado'
		self.next_fixed_term_line_id.action_cancel()

	@api.one
	@api.depends('invoice_id.state')
	def compute_change_state(self):
		if self.invoice_id.state == 'open' and self.state == 'por_facturar':
			self.state = 'finalizado'
			self.next_fixed_term_line_id.state = 'activo'

	@api.multi
	def validate_fixed_term_line(self):
		self.ensure_one()
		if self.compound_interest:
			self.state = 'finalizado'
			self.next_fixed_term_line_id.state = 'activo'
			#if es el ultimo => facturar.
		else:
			self.generate_invoice()
			if self.invoice_id.state == 'draft':
				self.state = 'por_facturar'
				self.sub_state = 'por_facturar'
			elif self.invoice_id.state == 'open':
				self.state = 'finalizado'
				self.next_fixed_term_line_id.state = 'activo'


	@api.one
	def generate_invoice(self):
		currency_id = self.env.user.company_id.currency_id.id
		configuracion_id = self.env['fixed.term.config'].browse(1)
		automatic_validate = configuracion_id.automatic_validate
		# Create invoice line
		ail_ids = []
		vat_tax_id = False
		invoice_line_tax_ids = False
		#if self.currency_id.name != "ARS":
		#	raise ValidationError("Por el momento solo se permite plazos fijos en pesos.")
		if self.vat_tax:
			vat_tax_id = self.vat_tax_id.id
			invoice_line_tax_ids = [(6, 0, [vat_tax_id])]
		price_unit = 0
		if self.compound_interest:
			for line_id in self.fixed_term_id.line_ids:
				if line_id.state == 'finalizado':
					price_unit += line_id.total_amount
		else:
			price_unit = self.total_amount
		if self.interest_amount > 0:
			ail = {
				'name': "Intereses pagados - Plazo Fijo",
				'quantity':1,
				'price_unit': price_unit,
				'vat_tax_id': vat_tax_id,
				'invoice_line_tax_ids': invoice_line_tax_ids,
				'report_invoice_line_tax_ids': invoice_line_tax_ids,
				'account_id': self.journal_id.default_debit_account_id.id,
			}
			ail_ids.append((0,0,ail))
			print ail
			print ail_ids

		if len(ail_ids) > 0:
			ai_values = {
				'type': 'in_invoice',
			    'account_id': self.fixed_term_id.account_id.id,
			    'partner_id': self.partner_id.id,
			    'journal_id': self.journal_id.id,
			    'currency_id': currency_id,
			    'company_id': 1,
			    'date': self.date,
			    'document_number': self.document_number,
			    'invoice_line_ids': ail_ids,
			}
			new_invoice_id = self.env['account.invoice'].create(ai_values)
			if automatic_validate:
				if self.document_number:
					if len(self.partner_id.afip_responsability_type_id) <= 0:
						raise ValidationError("Tipo de responsabilidad AFIP no definida en el Proveedor.")
				new_invoice_id.signal_workflow('invoice_open')
			self.invoice_id = new_invoice_id.id

class FixedTermConfig(models.Model):
	_name = 'fixed.term.config'

	name = fields.Char('Nombre', defualt='Configuracion general', readonly=True, required=True)
	journal_id = fields.Many2one('account.journal', 'Diario de plazo fijo')
	invoice_journal_id = fields.Many2one('account.journal', 'Diario de facturacion')
	automatic_validate = fields.Boolean('Validacion automatica de facturas', default=True)
