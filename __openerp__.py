# -*- coding: utf-8 -*-
##############################################################################
#
#    flydoc module for OpenERP, FlyDoc webservices access from OpenERP
#    Copyright (C) 2014 SYLEAM Info Services (<http://www.Syleam.fr/>)
#              Sylvain Garancher <sylvain.garancher@syleam.fr>
#
#    This file is a part of flydoc
#
#    flydoc is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    flydoc is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

{
    'name': 'Flydoc',
    'version': '1.0',
    'category': 'Custom',
    'description': """FlyDoc webservices access from OpenERP""",
    'author': 'SYLEAM',
    'website': 'http://www.syleam.fr/',
    'depends': ['base'],
    'init_xml': [],
    'images': [],
    'update_xml': [
        #'security/ir.model.access.csv',
        'security/groups.xml',
        'flydoc_view.xml',
    ],
    'demo_xml': [],
    'test': [],
    'external_dependancies': {'python': ['pyflydoc']},
    'installable': True,
    'active': False,
    'license': 'AGPL-3',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
