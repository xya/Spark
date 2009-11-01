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

from spark.async import Future
from spark.messaging.parser import MessageReader
from spark.messaging.messages import MessageWriter

__all__ = ["messageReader", "messageWriter", "negociateProtocol", "Supported", "NegociationError"]

VERSION_1 = "SPARKv1"
Supported = frozenset([VERSION_1])

def messageReader(file, protocol=VERSION_1):
    if protocol == VERSION_1:
        return MessageReader(file)
    else:
        raise ValueError("Protocol not supported")

def messageWriter(file, protocol=VERSION_1):
    if protocol == VERSION_1:
        return MessageWriter(file)
    else:
        raise ValueError("Protocol not supported")

def negociateProtocol(f, initiating):
    """
    Negociate a protocol with the remote peer, using the file for exchanging messages.
    'initiating' indicates whether the local user initiated the connection or not.
    """
    n = Negociator(f)
    return n.negociate(initiating)

class NegociationError(StandardError):
    """ Exception raised when protocol negociation fails. """
    pass

class Negociator(object):
    def __init__(self, file):
        self.file = file
    
    def negociate(self, initiating):
        cont = Future()
        if initiating:
            cont.run_coroutine(self.client_negociation())
        else:
            cont.run_coroutine(self.server_negociation())
        return cont
    
    def client_negociation(self):
        yield self.writeSupportedProtocols()
        remoteChoice = yield self.readProtocol()
        if remoteChoice not in Supported:
            raise NegociationError("Protocol '%s' is not supported" % remoteChoice)
        yield self.writeProtocol(remoteChoice)
        yield remoteChoice
    
    def server_negociation(self):
        proposed = yield self.readSupportedProtocols()
        choice = self.chooseProtocol(proposed)
        yield self.writeProtocol(choice)
        remoteChoice = yield self.readProtocol()
        if remoteChoice != choice:
            cont.failed(NegociationError("The remote peer chose another protocol: '%s' (was '%s')" % (remoteChoice, choice)))
        yield remoteChoice
    
    def chooseProtocol(self, proposedNames):
        for name in proposedNames:
            if name in Supported:
                return name
        raise NegociationError("No protocol in the proposed list is supported")
    
    def writeSupportedProtocols(self):
        data = self.formatMessage("supports %s" % " ".join(Supported))
        return self.asyncWrite(data)
    
    def writeProtocol(self, name):
        data = self.formatMessage("protocol %s" % name)
        return self.asyncWrite(data)
    
    def readSupportedProtocols(self):
        cont = Future()
        self.readMessage().after(self.parseSupportedProtocol, cont)
        return cont
    
    def parseSupportedProtocol(self, prev, cont):
        chunks = prev.result.split(" ")
        if chunks[0] != "supports":
            if chunks[0] == "not-supported":
                cont.failed(NegociationError("The remote peer returned an error"))
            else:
                cont.failed(NegociationError("Exepected '%s', read '%s'" % ("protocol", chunks[0])))
        elif len(chunks) < 2:
            cont.failed(NegociationError("Expected at least one protocol name"))
        else:
            cont.completed(chunks[1:])
    
    def readProtocol(self):
        cont = Future()
        self.readMessage().after(self.parseProtocol, cont)
        return cont
    
    def parseProtocol(self, prev, cont):
        chunks = prev.result.split(" ")
        if chunks[0] != "protocol":
            if chunks[0] == "not-supported":
                cont.failed(NegociationError("The remote peer returned an error"))
            else:
                cont.failed(NegociationError("Exepected '%s', read '%s'" % ("protocol", chunks[0])))
        elif len(chunks) < 2:
            cont.failed(NegociationError("Expected a protocol name"))
        else:
            cont.completed(chunks[1])
    
    def readMessage(self):
        cont = Future()
        self.asyncRead(4).fork(self.sizeRead, cont, cont)
        return cont
    
    def sizeRead(self, read, cont):
        try:
            size = int(read, 16)
        except:
            cont.failed()
        else:
            self.asyncRead(size).fork(self.dataRead, cont, cont)
    
    def dataRead(self, read, cont):
        if len(read) > 0:
            cont.completed(read.strip())
        else:
            cont.error(EOFError())
    
    def formatMessage(self, m):
        data = " %s\r\n" % str(m)
        return "%04x%s" % (len(data), data)
    
    def asyncRead(self, size=None):
        if hasattr(self.file, "beginRead"):
            return self.file.beginRead(size)
        try:
            data = self.file.read(size)
            return Future.done(data)
        except:
            return Future.error()
    
    def asyncWrite(self, data):
        if hasattr(self.file, "beginWrite"):
            return self.file.beginWrite(data)
        try:
            self.file.write(data)
            return Future.done()
        except:
            return Future.error()