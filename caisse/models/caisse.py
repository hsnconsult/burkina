# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from functools import partial

import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons import decimal_precision as dp


class ReportVendeursDet(models.AbstractModel):

    _name = 'report.caisse.report_vendeursdet'


    @api.model
    def get_vendeurs_details(self, date_start=False, date_stop=False, configs=False, vendeur=False):
        """ Serialise the orders of the day information

        params: date_start, date_stop string representing the datetime of order
        """
        if not configs:
            configs = self.env['pos.config'].search([])

        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
        today = today.astimezone(pytz.timezone('UTC'))
        if date_start:
            date_start = fields.Datetime.from_string(date_start)
        else:
            # start by default today 00:00:00
            date_start = today

        if date_stop:
            # set time to 23:59:59
            date_stop = fields.Datetime.from_string(date_stop)
        else:
            # stop by default today 23:59:59
            date_stop = today + timedelta(days=1, seconds=-1)

        # avoid a date_stop smaller than date_start
        date_stop = max(date_stop, date_start)

        date_start = fields.Datetime.to_string(date_start)
        date_stop = fields.Datetime.to_string(date_stop)

        orders = self.env['pos.order'].search([
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop),
            ('state', 'in', ['paid','invoiced','done']),
            ('user_id', '=', vendeur.id),
            ('config_id', 'in', configs.ids)])
        #raise UserError(_(orders)
        user_currency = self.env.user.company_id.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id.compute(order.amount_total, user_currency)
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                key = (line.product_id, line.price_unit, line.discount)
                products_sold.setdefault(key, 0.0)
                products_sold[key] += line.qty

                if line.tax_ids_after_fiscal_position:
                    line_taxes = line.tax_ids_after_fiscal_position.compute_all(line.price_unit * (1-(line.discount or 0.0)/100.0), currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                    for tax in line_taxes['taxes']:
                        taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount':0.0, 'base_amount':0.0})
                        taxes[tax['id']]['tax_amount'] += tax['amount']
                        taxes[tax['id']]['base_amount'] += tax['base']
                else:
                    taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount':0.0, 'base_amount':0.0})
                    taxes[0]['base_amount'] += line.price_subtotal_incl

        st_line_ids = self.env["account.bank.statement.line"].search([('pos_statement_id', 'in', orders.ids)]).ids
        if st_line_ids:
            self.env.cr.execute("""
                SELECT aj.name, sum(amount) total
                FROM account_bank_statement_line AS absl,
                     account_bank_statement AS abs,
                     account_journal AS aj 
                WHERE absl.statement_id = abs.id
                    AND abs.journal_id = aj.id 
                    AND absl.id IN %s 
                GROUP BY aj.name
            """, (tuple(st_line_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []

        return {
            'currency_precision': user_currency.decimal_places,
            'total_paid': user_currency.round(total),
            'payments': payments,
            'company_name': self.env.user.company_id.name,
            'taxes': list(taxes.values()),
            'vendeur': vendeur.name,
            'products': sorted([{
                'product_id': product.id,
                'product_name': product.name,
                'code': product.default_code,
                'quantity': qty,
                'price_unit': price_unit,
                'discount': discount,
                'uom': product.uom_id.name
            } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['product_name'])
        }

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        configs = self.env['pos.config'].browse(data['config_ids'])
        vendeur = self.env['res.users'].browse(data['vendeur'])
        #raise UserError(_(vendeur))
        data.update(self.get_vendeurs_details(data['date_start'], data['date_stop'], configs, vendeur))
        #raise UserError(_(data))
        return data

class ReportRayonsDet(models.AbstractModel):

    _name = 'report.caisse.report_rayonsdet'


    @api.model
    def get_rayons_details(self, date_start=False, date_stop=False, configs=False, rayon=False):
        """ Serialise the orders of the day information

        params: date_start, date_stop string representing the datetime of order
        """
        if not configs:
            configs = self.env['pos.config'].search([])

        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
        today = today.astimezone(pytz.timezone('UTC'))
        if date_start:
            date_start = fields.Datetime.from_string(date_start)
        else:
            # start by default today 00:00:00
            date_start = today

        if date_stop:
            # set time to 23:59:59
            date_stop = fields.Datetime.from_string(date_stop)
        else:
            # stop by default today 23:59:59
            date_stop = today + timedelta(days=1, seconds=-1)

        # avoid a date_stop smaller than date_start
        date_stop = max(date_stop, date_start)

        date_start = fields.Datetime.to_string(date_start)
        date_stop = fields.Datetime.to_string(date_stop)

        orders = self.env['pos.order'].search([
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop),
            ('state', 'in', ['paid','invoiced','done']),
            ('location_id', '=', rayon.id),
            ('config_id', 'in', configs.ids)])
        #raise UserError(_(orders)
        user_currency = self.env.user.company_id.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id.compute(order.amount_total, user_currency)
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                key = (line.product_id, line.price_unit, line.discount)
                products_sold.setdefault(key, 0.0)
                products_sold[key] += line.qty

                if line.tax_ids_after_fiscal_position:
                    line_taxes = line.tax_ids_after_fiscal_position.compute_all(line.price_unit * (1-(line.discount or 0.0)/100.0), currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                    for tax in line_taxes['taxes']:
                        taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount':0.0, 'base_amount':0.0})
                        taxes[tax['id']]['tax_amount'] += tax['amount']
                        taxes[tax['id']]['base_amount'] += tax['base']
                else:
                    taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount':0.0, 'base_amount':0.0})
                    taxes[0]['base_amount'] += line.price_subtotal_incl

        st_line_ids = self.env["account.bank.statement.line"].search([('pos_statement_id', 'in', orders.ids)]).ids
        if st_line_ids:
            self.env.cr.execute("""
                SELECT aj.name, sum(amount) total
                FROM account_bank_statement_line AS absl,
                     account_bank_statement AS abs,
                     account_journal AS aj 
                WHERE absl.statement_id = abs.id
                    AND abs.journal_id = aj.id 
                    AND absl.id IN %s 
                GROUP BY aj.name
            """, (tuple(st_line_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []

        return {
            'currency_precision': user_currency.decimal_places,
            'total_paid': user_currency.round(total),
            'payments': payments,
            'company_name': self.env.user.company_id.name,
            'taxes': list(taxes.values()),
            'rayon': rayon.name,
            'products': sorted([{
                'product_id': product.id,
                'product_name': product.name,
                'code': product.default_code,
                'quantity': qty,
                'price_unit': price_unit,
                'discount': discount,
                'uom': product.uom_id.name
            } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['product_name'])
        }

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        configs = self.env['pos.config'].browse(data['config_ids'])
        rayon = self.env['stock.location'].browse(data['rayon'])
        #raise UserError(_(vendeur))
        data.update(self.get_rayons_details(data['date_start'], data['date_stop'], configs, rayon))
        #raise UserError(_(data))
        return data


class ReportVendeurs(models.AbstractModel):

    _name = 'report.caisse.report_vendeurs'


    @api.model
    def get_vendeurs(self, date_start=False, date_stop=False, configs=False):
        """ Serialise the orders of the day information

        params: date_start, date_stop string representing the datetime of order
        """
        if not configs:
            configs = self.env['pos.config'].search([])

        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
        today = today.astimezone(pytz.timezone('UTC'))
        if date_start:
            date_start = fields.Datetime.from_string(date_start)
        else:
            # start by default today 00:00:00
            date_start = today

        if date_stop:
            # set time to 23:59:59
            date_stop = fields.Datetime.from_string(date_stop)
        else:
            # stop by default today 23:59:59
            date_stop = today + timedelta(days=1, seconds=-1)

        # avoid a date_stop smaller than date_start
        date_stop = max(date_stop, date_start)

        date_start = fields.Datetime.to_string(date_start)
        date_stop = fields.Datetime.to_string(date_stop)

        orders_ids = self.env['pos.order'].search([
            ('date_order', '>=', date_start),
            ('date_order', '<=', date_stop),
            ('state', 'in', ['paid','invoiced','done']),
            ('config_id', 'in', configs.ids)]).ids
        #raise UserError(_(orders)
        user_currency = self.env.user.company_id.currency_id

        if orders_ids:
            self.env.cr.execute("""
                select p.login as name, sum(l.qty*l.price_unit*(1-l.discount/100)) as total, count(distinct o.id) as nombre
                from res_users p, pos_order o, pos_order_line l
                where l.order_id = o.id
                and o.user_id = p.id
                and o.id in %s
                group by p.login
                order by p.login
            """, (tuple(orders_ids),))
            orders = self.env.cr.dictfetchall()
        else:
            orders = []

        return {
            'currency_precision': user_currency.decimal_places,
            'orders': orders,
            'company_name': self.env.user.company_id.name,
        }

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        configs = self.env['pos.config'].browse(data['config_ids'])
        #raise UserError(_(vendeur))
        data.update(self.get_vendeurs(data['date_start'], data['date_stop'], configs))
        #raise UserError(_(data))
        return data

class ReportStocks(models.AbstractModel):

    _name = 'report.caisse.report_stocks'


    @api.model
    def get_stocks(self, date_start=False, date_stop=False, location=False, avecm=False):


        #date_start = fields.Datetime.to_string(date_start)
        #date_stop = fields.Datetime.to_string(date_stop)
        #raise UserError(_(location.id))
        if avecm:
           cond = " where (coalesce(entree.qteent,0)+coalesce(sortie.qtesort,0)) != 0 " 
        else:
           cond = " " 
        cr = self.env.cr
        #location = location[0]
        requete = "with sinite as " \
                  "(SELECT product_id, sum(qty_done) as inite " \
                  "from stock_move_line " \
                  "where location_dest_id = '"+str(location.id)+"' " \
                  "and date < '"+date_start+"' " \
                  "group by product_id), " \
                  "sinits as " \
                  "(SELECT product_id, sum(qty_done) as inits " \
                  "from stock_move_line " \
                  "where location_id = '"+str(location.id)+"' " \
                  "and date < '"+date_start+"' " \
                  "group by product_id), " \
                  "init as( " \
                  "select p.id, sinite.inite, sinits.inits " \
                  "from product_product p " \
                  "left join  sinite " \
                  "on p.id = sinite.product_id " \
                  "left join sinits " \
                  "on p.id = sinits.product_id), " \
                  "entree as " \
                  "(select product_id, sum(qty_done) as qteent " \
                  "from stock_move_line " \
                  "where location_dest_id = '"+str(location.id)+"' " \
                  "and date between '"+date_start+"' AND '"+date_stop+"' " \
                  "group by product_id), " \
                  "sortie as " \
                  "(select product_id, sum(qty_done) as qtesort " \
                  "from stock_move_line " \
                  "where location_id = '"+str(location.id)+"' " \
                  "and date between '"+date_start+"' AND '"+date_stop+"' " \
                  "group by product_id), " \
                  "finale as " \
                  "(SELECT product_id, sum(qty_done) as sfinale " \
                  "from stock_move_line " \
                  "where location_dest_id = '"+str(location.id)+"' " \
                  "and date <= '"+date_stop+"' " \
                  "group by product_id), " \
                  "finals as " \
                  "(SELECT product_id, sum(qty_done) as sfinals " \
                  "from stock_move_line " \
                  "where location_id = '"+str(location.id)+"' " \
                  "and date <= '"+date_stop+"' " \
                  "group by product_id), " \
                  "final as( " \
                  "select p.id, finale.sfinale, finals.sfinals " \
                  "from product_product p " \
                  "left join  finale " \
                  "on p.id = finale.product_id " \
                  "left join finals " \
                  "on p.id = finals.product_id) " \
                  "select p.barcode, pr.name as produit, coalesce(si.inite,0)-coalesce(si.inits,0) as stinit, coalesce(entree.qteent,0) as qteent, coalesce(sortie.qtesort,0) as qtesort, coalesce(final.sfinale,0)-coalesce(final.sfinals,0) as stfinal " \
                  "from product_product p " \
                  "left join product_template pr " \
                  "on p.product_tmpl_id = pr.id " \
                  "left join init si " \
                  "on p.id = si.id " \
                  "left join entree " \
                  "on p.id = entree.product_id " \
                  "left join sortie " \
                  "on p.id = sortie.product_id " \
                  "left join final " \
                  "on p.id = final.id "+cond+" " \
                  "order by pr.name"
        #raise UserError(_(requete))
        cr.execute(requete)
        alines = cr.dictfetchall()
        return {
            'alines': alines,
            'company_name': self.env.user.company_id.name,
        }

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        location = self.env['stock.location'].browse(data['location'])
        data.update(self.get_stocks(data['date_start'], data['date_stop'] ,location[0],data['avecm']))
        #raise UserError(_(data))
        return data

class ReportVentes(models.AbstractModel):

    _name = 'report.caisse.report_ventes'


    @api.model
    def get_ventes(self, date_start=False, date_stop=False):


        #date_start = fields.Datetime.to_string(date_start)
        #date_stop = fields.Datetime.to_string(date_stop)
        #raise UserError(_(location.id))
        cr = self.env.cr
        #location = location[0]
        requete = "SELECT p.barcode, pr.name as produit, l.qty as quantite, i.value_float as prixrevient, l.price_unit-(l.price_unit*l.discount/100) as prixvente, l.price_unit-(l.price_unit*l.discount/100)-i.value_float as margeunit, (l.price_unit-(l.price_unit*l.discount/100)-i.value_float)*l.qty as margetot, l.qty*(l.price_unit-(l.price_unit*l.discount/100)) as totvente " \
                  "FROM product_product p, pos_order_line l, pos_order po, product_template pr, ir_property i " \
                  "WHERE l.product_id = p.id " \
                  "AND p.product_tmpl_id = pr.id " \
                  "AND l.order_id = po.id " \
                  "AND i.name = 'standard_price' " \
                  "AND p.id = cast(substring(i.res_id,17,4) as integer) " \
                  "AND po.date_order BETWEEN '"+date_start+"' AND '"+date_stop+"'"
        #raise UserError(_(requete))
        cr.execute(requete)
        alines = cr.dictfetchall()
        requete2 = "SELECT p.barcode, pr.name as produit, c.name as client, l.product_uom_qty as quantite, i.value_float as prixrevient, l.price_unit-(l.price_unit*l.discount/100) as prixvente, l.price_unit-(l.price_unit*l.discount/100)-i.value_float as margeunit, (l.price_unit-(l.price_unit*l.discount/100)-i.value_float)*l.product_uom_qty as margetot, l.product_uom_qty*(l.price_unit-(l.price_unit*l.discount/100)) as totvente " \
                  "FROM product_product p, sale_order_line l, sale_order po, product_template pr, ir_property i, res_partner c " \
                  "WHERE l.product_id = p.id " \
                  "AND p.product_tmpl_id = pr.id " \
                  "AND l.order_id = po.id " \
                  "AND po.partner_id = c.id " \
                  "AND i.name = 'standard_price' " \
                  "AND p.id = cast(substring(i.res_id,17,4) as integer) " \
                  "AND po.confirmation_date BETWEEN '"+date_start+"' AND '"+date_stop+"'"
        #raise UserError(_(requete2))
        cr.execute(requete2)
        clines = cr.dictfetchall()
        return {
            'alines': alines,
            'clines': clines,
            'company_name': self.env.user.company_id.name,
        }

    @api.multi
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_ventes(data['date_start'], data['date_stop']))
        #raise UserError(_(data))
        return data
