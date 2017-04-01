# -*- coding: utf-8 -*-
# Copyright 2017 SYLEAM Info Services
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Flydoc',
    'version': '10.0.1.0.0',
    'category': 'Custom',
    'description': """FlyDoc webservices access from Odoo""",
    'author': 'SYLEAM',
    'website': 'http://www.syleam.fr/',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/flydoc.xml',
    ],
    'external_dependancies': {'python': ['pyflydoc']},
    'installable': True,
    'active': False,
    'license': 'AGPL-3',
}
