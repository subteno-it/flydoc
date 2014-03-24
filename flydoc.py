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

from openerp.osv import orm
from openerp.osv import fields
from pyflydoc import FlyDoc, FlyDocTransportName, FlyDocTransportState, FlyDocSubmissionService
import logging
logger = logging.getLogger('flydoc')


class FlyDocService(orm.Model):
    _name = 'flydoc.service'
    _description = 'FlyDoc Service'

    _columns = {
        'name': fields.char('Name', size=64, required=True, help='Name of the FlyDoc service'),
        'username': fields.char('Username', size=64, required=True, help='Username for login'),
        'password': fields.char('Password', size=64, required=True, help='Password of the user'),
        'state': fields.selection([('unverified', 'Unverified'), ('verified', 'Verified')], 'State', required=True, help='Set to unverified until the connection has been successfully established with the Verify button'),
    }

    _defaults = {
        'state': 'unverified',
    }

    _sql_constraints = [
        ('username_unique', 'UNIQUE (username)', 'The username of the FlyDoc service must be unique !'),
    ]

    def write(self, cr, uid, ids, values, context=None):
        """
        Set the state to unverified if we change username and/or password
        """
        if 'username' in values or 'password' in values:
            values['state'] = 'unverified'

        return super(FlyDocService, self).write(cr, uid, ids, values, context=context)

    def check_connection(self, cr, uid, ids, context=None):
        """
        Check if the information are valid
        """
        verified_ids = []
        for service in self.browse(cr, uid, ids, context=context):
            try:
                FlyDoc().login(service.username, service.password)
            except Exception, e:
                logger.warning('Connection failed for FlyDoc service %s (%d) : %s' % (service.name, service.id, e.message))
                continue

            verified_ids.append(service.id)

        return self.write(cr, uid, verified_ids, {'state': 'verified'}, context=context)

    def update_transports(self, cr, uid, ids, context=None):
        """
        Updates the transports list from the FlyDoc webservice
        """
        transport_obj = self.pool.get('flydoc.transport')
        transport_var_obj = self.pool.get('flydoc.transport.var')

        updated_transportids = []
        for service in self.browse(cr, uid, ids, context=context):
            transport_ids = transport_obj.search(cr, uid, [('service_ids', 'in', ids), ('transportid', 'not in', updated_transportids), ('state', 'not in', (
                str(FlyDocTransportState.Successful.value),
                str(FlyDocTransportState.Failure.value),
                str(FlyDocTransportState.Canceled.value),
                str(FlyDocTransportState.Rejected.value),
            ))], context=context)

            # Open a connection to the FlyDoc webservices
            connection = FlyDoc()
            connection.login(service.username, service.password)

            # Update all found transports
            for transport in transport_obj.browse(cr, uid, transport_ids, context=context):
                flydocTransport = connection.browse(filter='msn=%d' % transport.transportid).next()
                updated_transportids.append(transport.transportid)

                # Update the transport values
                transport.write({'name': flydocTransport.transportName, 'state': flydocTransport.state}, context=context)

                # Update the transport vars
                for transport_var in flydocTransport.vars.Var:
                    var_values = {
                        'transport_id': transport.id,
                        'name': transport_var.attribute,
                        'value': transport_var.simpleValue,
                        'type': transport_var.type
                    }

                    # Update each var of this transport
                    transport_var_ids = transport_var_obj.search(cr, uid, [('transport_id', '=', transport.id), ('name', '=', transport_var.attribute)], context=context)
                    if not transport_var_ids:
                        transport_var_obj.create(cr, uid, var_values, context=context)
                    else:
                        transport_var_obj.write(cr, uid, transport_var_ids, var_values, context=context)

            # Close the connection
            connection.logout()

        return True


class FlyDocTransport(orm.Model):
    _name = 'flydoc.transport'
    _description = 'FlyDoc Transport'

    def _getTransportNames(self, cr, uid, context=None):
        return [(name.name, name.value) for name in FlyDocTransportName]

    def _getTransportStates(self, cr, uid, context=None):
        return [(str(state.value), state.name) for state in FlyDocTransportState]

    _columns = {
        'service_ids': fields.many2many('flydoc.service', string='Services', readonly=True, help='Services from which this transport is available'),
        'transportid': fields.integer('Transport ID', required=True, readonly=True, help='Identifier of this transport at FlyDoc'),
        'state': fields.selection(_getTransportStates, 'State', readonly=True, help='State of this transport'),
        'name': fields.selection(_getTransportNames, 'Transport Name', readonly=True, help='Name of the transport'),
        'var_ids': fields.one2many('flydoc.transport.var', 'transport_id', 'Vars', readonly=True, help='Vars of this transport'),
        'attachment_ids': fields.one2many('flydoc.transport.attachment', 'transport_id', 'Attachments', readonly=True, help='Attachments of this transport'),
    }

    _sql_constraints = [
        ('transportid_unique', 'UNIQUE (transportid)', 'The transportID of the FlyDoc transport must be unique !'),
    ]


class FlyDocTransportVar(orm.Model):
    _name = 'flydoc.transport.var'
    _description = 'FlyDoc Transport Var'

    def _getTransportVarTypes(self, cr, uid, context=None):
        return [(typeCode, typeName) for typeName, typeCode in FlyDocSubmissionService().VAR_TYPE]

    _columns = {
        'transport_id': fields.many2one('flydoc.transport', 'Transport', required=True, help='Transport of this var'),
        'name': fields.char('Name', size=64, required=True, help='Name of the var'),
        'value': fields.char('Value', size=64, help='Value of the var'),
        'type': fields.selection(_getTransportVarTypes, 'Type', help='Type of the var'),
    }


class FlyDocTransportAttachment(orm.Model):
    _name = 'flydoc.transport.attachment'
    _description = 'FlyDoc Transport Attachment'

    _columns = {
        'transport_id': fields.many2one('flydoc.transport', 'Transport', required=True, help='Transport of this attachment'),
        'filename': fields.char('Filename', size=64, required=True, help='Name of the attached file'),
        'data': fields.binary('Data', required=True, help='Contents of the attached file'),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
