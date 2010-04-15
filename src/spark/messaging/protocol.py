# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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

import logging
from spark.messaging.parser import MessageReader
from spark.messaging.messages import MessageWriter

__all__ = ["messageReader", "messageWriter", "negociateProtocol", "Supported", "NegociationError"]

VERSION_ALPHA = "SPARK_ALPHA"
Supported = frozenset([VERSION_ALPHA])

def messageReader(file, protocol=VERSION_ALPHA):
    if protocol == VERSION_ALPHA:
        return MessageReader(file)
    else:
        raise ValueError("Protocol '%s' not supported" % protocol)

def messageWriter(file, protocol=VERSION_ALPHA):
    if protocol == VERSION_ALPHA:
        return MessageWriter(file)
    else:
        raise ValueError("Protocol '%s' not supported" % protocol)

def negociateProtocol(f, initiating):
    """
    Negociate a protocol with the remote peer, using the file for exchanging messages.
    'initiating' indicates whether the local user initiated the connection or not.
    """
    return Negociator(f).negociate(initiating)

class NegociationError(StandardError):
    """ Exception raised when protocol negociation fails. """
    pass

class Negociator(object):
    def __init__(self, file):
        self.file = file
    
    def negociate(self, initiating):
        if initiating:
            return self.clientNegociation()
        else:
            return self.serverNegociation()
    
    def clientNegociation(self):
        self.writeSupportedProtocols()
        remoteChoice = self.readProtocol()
        if remoteChoice not in Supported:
            raise NegociationError("Protocol '%s' is not supported" % remoteChoice)
        self.writeProtocol(remoteChoice)
        return remoteChoice
    
    def serverNegociation(self):
        proposed = self.readSupportedProtocols()
        choice = self.chooseProtocol(proposed)
        self.writeProtocol(choice)
        remoteChoice = self.readProtocol()
        if remoteChoice != choice:
            raise NegociationError("The remote peer chose another protocol: '%s' (was '%s')" % (remoteChoice, choice))
        return remoteChoice
    
    def chooseProtocol(self, proposedNames):
        for name in proposedNames:
            if name in Supported:
                return name
        raise NegociationError("No protocol in the proposed list is supported")
    
    def readSupportedProtocols(self):
        message = self.readMessage()
        chunks = message.split(" ")
        if chunks[0] != "supports":
            if chunks[0] == "not-supported":
                raise NegociationError("The remote peer returned an error")
            else:
                raise NegociationError("Exepected '%s', read '%s'" % ("protocol", chunks[0]))
        elif len(chunks) < 2:
            raise NegociationError("Expected at least one protocol name")
        else:
            return chunks[1:]
    
    def readProtocol(self):
        message = self.readMessage()
        chunks = message.split(" ")
        if chunks[0] != "protocol":
            if chunks[0] == "not-supported":
                raise NegociationError("The remote peer returned an error")
            else:
                raise NegociationError("Exepected '%s', read '%s'" % ("protocol", chunks[0]))
        elif len(chunks) < 2:
            raise NegociationError("Expected a protocol name")
        else:
            return chunks[1]
    
    def readMessage(self):
        sizeText = self.file.read(4)
        if len(sizeText) == 0:
            raise EOFError()
        size = int(sizeText, 16)
        data = self.file.read(size)
        if len(data) == 0:
            raise EOFError()
        return data.strip()
    
    def writeSupportedProtocols(self):
        data = self.formatMessage("supports %s" % " ".join(Supported))
        self.file.write(data)
    
    def writeProtocol(self, name):
        data = self.formatMessage("protocol %s" % name)
        self.file.write(data)
    
    def formatMessage(self, m):
        data = " %s\r\n" % str(m)
        return "%04x%s" % (len(data), data)