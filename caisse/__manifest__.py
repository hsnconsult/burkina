# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'caisse',
    'version' : '1.1',
    'summary': 'Permet de gérer la caisse',
    'sequence': 180,
    'description': """
Gestion de la paie
====================
    """,
    'license': 'OPL-1',
    'author': 'HSN Consult',
    'category': 'Comptabilité',
    'website': 'http://www.hsnconsult.com',
    'depends': ['point_of_sale'],
    'data': [
        'security/caisse_security.xml',
        'wizard/etats_caisse.xml',
        'views/caisse_report.xml',
        'views/report_vendeursdet.xml',
        'views/report_vendeurs.xml',
        'views/report_rayonsdet.xml',
        'views/report_stock.xml',
        'views/report_ventes.xml',
        'views/report_cloture.xml',
        'views/report_etiquette.xml',
        ],
    'installable': True,
    'application': True,
    'auto_install': False
}
