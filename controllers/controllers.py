# -*- coding: utf-8 -*-
from openerp import http

# class FixedTerm(http.Controller):
#     @http.route('/fixed_term/fixed_term/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fixed_term/fixed_term/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('fixed_term.listing', {
#             'root': '/fixed_term/fixed_term',
#             'objects': http.request.env['fixed_term.fixed_term'].search([]),
#         })

#     @http.route('/fixed_term/fixed_term/objects/<model("fixed_term.fixed_term"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fixed_term.object', {
#             'object': obj
#         })