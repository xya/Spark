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
from messages import MessageWriter

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
    n = Negociator(f, "\r\n")
    return n.negociate(initiating)

class Negociator(object):
    def __init__(self, file, newline):
        self.file = file
        self.newline = newline
    
    def negociate(self, initiating):
        if initiating:
            self.writeSupportedProtocols()
            remoteChoice = self.readProtocol()
            if remoteChoice not in Supported:
                raise ValueError("Protocol '%s' is not supported" % remoteChoice)
            self.writeProtocol(remoteChoice)
            return remoteChoice
        else:
            proposed = self.readSupportedProtocols()
            choice = self.chooseProtocol(proposed)
            self.writeProtocol(choice)
            remoteChoice = self.readProtocol()
            if remoteChoice != choice:
                raise ValueError("The remote peer chose another protocol: '%s' (was '%s')" % (remoteChoice, choice))
            return remoteChoice
    
    def chooseProtocol(self, proposedNames):
        for name in proposedNames:
            if name in Supported:
                return name
        raise ValueError("No protocol in the proposed list is supported")
    
    def writeSupportedProtocols(self):
        self.file.write("supports %s%s" % (" ".join(Supported), self.newline))
    
    def writeProtocol(self, name):
        self.file.write("protocol %s%s" % (name, self.newline))
    
    def readSupportedProtocols(self):
        chunks = self.readLine().split(" ")
        if chunks[0] != "supports":
            raise ValueError("Exepected '%s', read '%s'" % ("supports", chunks[0]))
        elif len(chunks) < 2:
            raise ValueError("Expected at least one protocol name")
        else:
            return chunks[1:]
    
    def readProtocol(self):
        chunks = self.readLine().split(" ")
        if chunks[0] != "protocol":
            raise ValueError("Exepected '%s', read '%s'" % ("protocol", chunks[0]))
        elif len(chunks) < 2:
            raise ValueError("Expected a protocol name")
        else:
            return chunks[1]
    
    def readLine(self):
        data = []
        matched = 0
        total = len(self.newline)
        c = self.file.read(1)
        while len(c) == 1:
            if c == self.newline[matched]:
                matched += 1
                if matched == total:
                    break
            else:
                data.append(c)
            c = self.file.read(1)
        if len(c) == 0:
            raise EOFError()
        else:
            return "".join(data)