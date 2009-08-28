# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>
#
# This file is part of the Spark File-transfer Tool.
#
# Spark is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Spark is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Spark; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from parser import MessageReader
from messages import MessageWriter, SupportedProtocolNames, ProtocolName

__all__ = ["messageReader", "messageWriter", "negociateProtocol", "Supported"]

Supported = frozenset(["SPARKv1"])

def messageReader(file, buffer=4096):
    return MessageReader(file, buffer)

def messageWriter(file):
    return MessageWriter(file)

def negociateProtocol(f, initiating):
    """
    Negociate a protocol with the remote peer, using the file for exchanging messages.
    'initiating' indicates whether the local user initiated the connection or not.
    """
    reader = messageReader(f)
    writer = messageWriter(f)
    if initiating:
        writer.write(SupportedProtocolNames(Supported))
        response = reader.read()
        validateProtocol(response)
        writer.write(ProtocolName(response.name))
        return response.name
    else:
        proposed = reader.read()
        choice = chooseProtocol(proposed)
        writer.write(ProtocolName(choice))
        response = reader.read()
        validateProtocol(response)
        if response.name != choice:
            raise ValueError("The remote peer chose another protocol: '%s' (was '%s')" % (choice, response.name))
        return response.name
        
def validateProtocol(response):
    if response is None:
        raise IOError("The remote peer closed the connection")
    elif not isinstance(response, ProtocolName):
        raise TypeError("Expected a ProtocolName message, got '%s'" % response.__class__)
    elif response.name not in Supported:
        raise ValueError("Protocol '%s' is not supported" % response.name)

def chooseProtocol(proposed):
    if proposed is None:
        raise IOError("The remote peer closed the connection")
    elif not isinstance(proposed, SupportedProtocolNames):
        raise TypeError("Expected a SupportedProtocolNames message, got '%s'" % proposed.__class__)
    else:
        for proposedName in proposed.names:
            if proposedName in Supported:
                return proposedName
        raise ValueError("No protocol in the proposed list is supported")