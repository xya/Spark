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
        self.buffer = ""
    
    def negociate(self, initiating):
        if initiating:
            print "Writing supported protocols"
            self.writeSupportedProtocols()
            print "Reading the remote choice"
            remoteChoice = self.readProtocol()
            if remoteChoice not in Supported:
                raise ValueError("Protocol '%s' is not supported" % remoteChoice)
            print "Writing the local choice"
            self.writeProtocol(remoteChoice)
            return remoteChoice
        else:
            print "Reading the proposed protocols"
            proposed = self.readSupportedProtocols()
            choice = self.chooseProtocol(proposed)
            print "Writing the local choice"
            self.writeProtocol(choice)
            print "Reading the remote choice"
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
        names = []
        self.match("supports ")
        names.append(self.readTag())
        c = self.read(1)
        while c == " ":
            names.append(self.readTag())
            c = self.read(1)
        self.buffer = c + self.buffer
        self.match(self.newline)
        return names
    
    def readProtocol(self):
        self.match("protocol ")
        name = self.readTag()
        self.match(self.newline)
        return name
    
    def readTag(self):
        tag = []
        c = self.read(1)
        while not c.isspace():
            tag.append(c)
            c = self.read(1)
        self.buffer = c + self.buffer
        return "".join(tag)
    
    def read(self, size):
        data = []
        left = size
        while left > 0:
            if len(self.buffer) > 0:
                count = max(len(self.buffer), left)
                read, self.buffer = self.buffer[:count], self.buffer[count:]
            else:
                read = self.file.read(left)
                count = len(read)
            if count == 0:
                raise EOFError()
            data.append(read)
            left -= count
        return "".join(data)
    
    def match(self, expected):
        actual = self.read(len(expected))
        if actual != expected:
            raise ValueError("Expected: '%s', read: '%s'" % (repr(expected), repr(actual)))