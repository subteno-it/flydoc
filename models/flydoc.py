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

import os
import base64
from openerp import models, api, fields, exceptions
from pyflydoc import FlyDoc, FlyDocTransportName, FlyDocTransportState, FlyDocSubmissionService
from openerp.tools.translate import _
import logging
logger = logging.getLogger('flydoc')


class FlyDocService(models.Model):
    _name = 'flydoc.service'
    _description = 'FlyDoc Service'

    name = fields.Char(string='Name', size=64, required=True, help='Name of the FlyDoc service')
    username = fields.Char(string='Username', size=64, required=True, help='Username for login')
    password = fields.Char(string='Password', size=64, required=True, help='Password of the user')
    need_validation = fields.Boolean(string='Need Validation', default=True, help='If checked, the sent transports will wait for a manual validation before being processed')
    state = fields.Selection(selection=[
        ('unverified', 'Unverified'),
        ('verified', 'Verified'),
    ], string='State', required=True, default='unverified', help='Set to unverified until the connection has been successfully established with the Verify button')

    _sql_constraints = [
        ('username_unique', 'UNIQUE (username)', 'The username of the FlyDoc service must be unique !'),
    ]

    @api.multi
    def write(self, values):
        """
        Set the state to unverified if we change username and/or password
        """
        if 'username' in values or 'password' in values:
            values['state'] = 'unverified'

        return super(FlyDocService, self).write(values)

    @api.multi
    def check_connection(self):
        """
        Check if the information are valid
        """
        verified_ids = []
        for service in self:
            try:
                FlyDoc().login(service.username, service.password)
            except Exception, e:
                logger.warning('Connection failed for FlyDoc service %s (%d) : %s' % (service.name, service.id, e.message))
                continue

            verified_ids.append(service.id)

        return self.browse(verified_ids).write({'state': 'verified'})

    @api.multi
    def submit(self, transportName, recipient_id, custom_vars=None, data=None, update_transport=True):
        """
        Submits a new transport to the FlyDoc webservice
        @param data : List of dicts containing the data to be sent :
            - {'type': 'path', 'path': '/path/to/file'}
            - {'type': 'data', 'filename': 'name_of_the_file', 'data': 'some data'}
            - {'type': 'ir.attachment', 'attachment_id': id_of_an_ir_attachment}
        """
        # Submit each transport only one time
        self.ensure_one()

        partner_obj = self.env['res.partner']
        transport_obj = self.env['flydoc.transport']
        recipient = partner_obj.browse(recipient_id)

        recipient_name = recipient.name
        if not recipient.is_company:
            # Add the title
            if recipient.title:
                recipient_name = '%s %s' % (recipient.title.shortcut, recipient.name)
            # Add the company name
            if recipient.parent_id:
                recipient_name = '%s\n%s' % (recipient.parent_id.name, recipient_name)

        # No address defined, put the company's address
        if not recipient.street or not recipient.zip or not recipient.city:
            recipient = recipient.parent_id

        transportVars = {
            'ToBlockAddress': '%s\n%s\n%s\n%s %s\n%s' % (
                recipient_name or '',
                recipient.street or '',
                recipient.street2 or '',
                recipient.zip or '', recipient.city or '',
                recipient.country_id.name or '',
            ),
        }

        # Add custom vars
        if custom_vars is not None:
            transportVars.update(custom_vars)

        # Set some specific vars
        if self.need_validation:
            transportVars['NeedValidation'] = '1'

        # Set ApplicationName to OpenERP
        transportVars['ApplicationName'] = 'Odoo 7.0'

        attachment_obj = self.env['ir.attachment']
        attachment_ids = []
        for contents in data:
            # If an ir.attachment id was suplied, simply add this in the data to send
            if contents['type'] == 'ir.attachment':
                attachment_ids.append(contents['attachment_id'])
                continue

            filename = None
            datas = None

            # Retrieve data to create a new ir.attachment, if needed
            if contents['type'] == 'path':
                filename = os.path.basename(contents['path'])
                with open(contents['path']) as fil:
                    datas = base64.b64encode(fil.read())
            elif contents['type'] == 'data':
                filename = contents['filename']
                datas = base64.b64encode(contents['data'])
            else:
                raise exceptions.Warning(_('Unknown data source !'))

            # Create the new ir.attachment if datas were supplied
            if datas is not None:
                attachment_data = {
                    'name': filename,
                    'datas_fname': filename,
                    'datas': datas,
                    'type': 'binary',
                }
                attachment_ids.append(attachment_obj.create(attachment_data))

        # Add each listed ir.attachment as transport attachments
        transportContents = []
        for attachment in attachment_obj.browse(attachment_ids):
            transportContents.append({'name': attachment.datas_fname, 'data': base64.b64decode(attachment.datas)})

        # Connect to the FlyDoc service
        connection = FlyDoc()
        connection.login(self.username, self.password)
        # Submit the transport to FlyDoc service
        submitInfo = connection.submit(transportName, transportVars, transportContents=transportContents)
        transport_id = transport_obj.create({'transportid': submitInfo.transportID, 'service_ids': [(4, self.id)]})
        # Add argument to select update or not
        if update_transport:
            self.update_transports(trans_ids=[transport_id])
        # Close the FlyDoc connection
        try:
            connection.logout()
        except:
            pass

        return(transport_id)

    @api.multi
    def update_transports(self, trans_ids=None):
        """
        Updates the transports list from the FlyDoc webservice
        """
        transport_obj = self.env['flydoc.transport']
        transport_var_obj = self.env['flydoc.transport.var']

        updated_transportids = []
        for service in self:
            domain = [
                ('service_ids', '=', service.id),
                ('transportid', 'not in', updated_transportids),
                ('state', 'not in', (
                    str(FlyDocTransportState.Successful.value),
                    str(FlyDocTransportState.Failure.value),
                    str(FlyDocTransportState.Canceled.value),
                    str(FlyDocTransportState.Rejected.value),
                ))
            ]
            if trans_ids:
                domain.append(('id', 'in', trans_ids))
            transports = transport_obj.search(domain)

            # Open a connection to the FlyDoc webservices
            connection = FlyDoc()
            connection.login(self.username, self.password)

            # Update all found transports
            for transport in transport_obj.browse(transports):
                updated_transportids.append(transport.transportid)
                try:
                    flydocTransport = connection.browse(filter='msn=%d' % transport.transportid).next()
                except StopIteration:
                    # Transport has been deleted
                    transport.unlink()
                    continue

                # Update the transport values
                transport.write({'name': flydocTransport.transportName, 'state': str(flydocTransport.state)})

                # Update the transport vars
                for transport_var in flydocTransport.vars.Var:
                    var_values = {
                        'transport_id': transport.id,
                        'name': transport_var.attribute,
                        'value': transport_var.simpleValue,
                        'type': transport_var.type
                    }

                    # Update each var of this transport
                    transport_vars = transport_var_obj.search([('transport_id', '=', transport.id), ('name', '=', transport_var.attribute)])
                    if not transport_vars:
                        transport_var_obj.create(var_values)
                    else:
                        transport_vars.write(var_values)

            # Close the connection
            try:
                connection.logout()
            except:
                pass

        return True


class FlyDocTransport(models.Model):
    _name = 'flydoc.transport'
    _description = 'FlyDoc Transport'

    @api.model
    def _getTransportNames(self):
        return [(name.name, name.value) for name in FlyDocTransportName]

    @api.model
    def _getTransportStates(self):
        return [(str(state.value), state.name) for state in FlyDocTransportState]

    service_ids = fields.Many2many(comodel_name='flydoc.service', string='Services', readonly=True, help='Services from which this transport is available')
    transportid = fields.Integer(string='Transport ID', required=True, readonly=True, help='Identifier of this transport at FlyDoc')
    state = fields.Selection(selection=_getTransportStates, string='State', readonly=True, help='State of this transport')
    name = fields.Selection(selection=_getTransportNames, string='Transport Name', readonly=True, help='Name of the transport')
    var_ids = fields.One2many(comodel_name='flydoc.transport.var', inverse_name='transport_id', string='Vars', readonly=True, help='Vars of this transport')
    attachment_ids = fields.One2many(comodel_name='flydoc.transport.attachment', inverse_name='transport_id', string='Attachments', readonly=True, help='Attachments of this transport')

    _sql_constraints = [
        ('transportid_unique', 'UNIQUE (transportid)', 'The transportID of the FlyDoc transport must be unique !'),
    ]


class FlyDocTransportVar(models.Model):
    _name = 'flydoc.transport.var'
    _description = 'FlyDoc Transport Var'

    @api.model
    def _getTransportVarTypes(self):
        return [(typeCode, typeName) for typeName, typeCode in FlyDocSubmissionService().VAR_TYPE]

    transport_id = fields.Many2one(comodel_name='flydoc.transport', string='Transport', required=True, ondelete='cascade', help='Transport of this var')
    name = fields.Char(string='Name', size=64, required=True, help='Name of the var')
    value = fields.Char(string='Value', size=64, help='Value of the var')
    type = fields.Selection(selection=_getTransportVarTypes, string='Type', help='Type of the var')


class FlyDocTransportAttachment(models.Model):
    _name = 'flydoc.transport.attachment'
    _description = 'FlyDoc Transport Attachment'

    transport_id = fields.Many2one(comodel_name='flydoc.transport', string='Transport', required=True, ondelete='cascade', help='Transport of this attachment')
    filename = fields.Char(string='Filename', size=64, required=True, help='Name of the attached file')
    data = fields.Binary(string='Data', required=True, help='Contents of the attached file')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
