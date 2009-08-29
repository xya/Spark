#!/usr/bin/env python
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

import unittest
import copy
from spark.messaging import *
from StringIO import StringIO

TestText = """> list-files 0 18 {"register": true}
< list-files 0 108 {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}
! file-added 55 106 {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}
> create-transfer 26 79 {"file-id": "<guid>", "blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}
< create-transfer 26 30 {"id": 2, "state": "inactive"}
> start-transfer 27 9 {"id": 2}
< start-transfer 27 30 {"id": 2, "state": "starting"}
! transfer-state-changed 56 28 {"id": 2, "state": "active"}
0x0014\x00\x01\x00\x02\x00\x00\x00\x00Hello, world
0x0408\x00\x01\x00\x02\x00\x00\x0B\xFF""" + ("!" * 1024) + """
> close-transfer 28 9 {"id": 2}
< close-transfer 28 9 {"id": 2}
"""

TestItems = [
    TextMessage(TextMessage.REQUEST, "list-files", {"register": True}, 0),
    TextMessage(TextMessage.RESPONSE, "list-files", {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}, 0),
    TextMessage(TextMessage.NOTIFICATION, "file-added", {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}, 55),
    TextMessage(TextMessage.REQUEST, "create-transfer", {"file-id": "<guid>", "blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}, 26),
    TextMessage(TextMessage.RESPONSE, "create-transfer", {"id": 2, "state": "inactive"}, 26),
    TextMessage(TextMessage.REQUEST, "start-transfer", {"id": 2}, 27),
    TextMessage(TextMessage.RESPONSE, "start-transfer", {"id": 2, "state": "starting"}, 27),
    TextMessage(TextMessage.NOTIFICATION, "transfer-state-changed", {"id": 2, "state": "active"}, 56),
    Block(2, 0, "Hello, world"),
    Block(2, 3071, "!" * 1024),
    TextMessage(TextMessage.REQUEST, "close-transfer", {"id": 2}, 28),
    TextMessage(TextMessage.RESPONSE, "close-transfer", {"id": 2}, 28),
]

# some tests might change attributes in the messages (e.g. the transaction ID)
# so we have to return copies of them to be safe
def TestItemProperty(itemIndex):
    return lambda: copy.copy(TestItems[itemIndex])
    
testRequest = TestItemProperty(0)
testResponse = TestItemProperty(1)
testNotification = TestItemProperty(2)
testBlock = TestItemProperty(8)

class ProtocolTest(unittest.TestCase):
    def assertMessagesEqual(self, expected, actual):
        if expected is None:
            self.assertEqual(expected, actual)
        else:
            self.assertEqual(str(expected), str(actual))
    
    def assertSeqsEqual(self, expectedSeq, actualSeq):
        self.assertEqual(len(expectedSeq), len(actualSeq))
        for expected, actual in zip(expectedSeq, actualSeq):
            self.assertMessagesEqual(expected, actual)
    
    def testParseText(self):
        """ Ensure that messageReader() can read messages from a text file """
        p = messageReader(StringIO(TestText))
        actualItems = list(p.readAll())
        self.assertSeqsEqual(TestItems, actualItems)
    
    def testReadWriteSync(self):
        """ Ensure that messages written by messageWriter() can be read by messageReader() """
        # first individual messages
        for item in TestItems:
            f = StringIO()
            messageWriter(f).write(item)
            f.seek(0)
            actual = messageReader(f).read()
            self.assertMessagesEqual(item, actual)
        
        # then a stream of messages
        f = StringIO()
        messageWriter(f).writeAll(TestItems)
        f.seek(0)
        actualItems = list(messageReader(f).readAll())
        self.assertSeqsEqual(TestItems, actualItems)

class ClientSocket(object):
    def __init__(self, supportedList):
        self.supported = supportedList
        self.readBuffer = "supports %s\r\n" % " ".join(supportedList)
        self.writeBuffer = ""
        self.state = 0
    
    def read(self, count):
        if count <= len(self.readBuffer):
            data, self.readBuffer = self.readBuffer[:count], self.readBuffer[count:]
            return data
        else:
            raise EOFError("Read would have blocked forever")
    
    def write(self, data):
        self.writeBuffer += data
        end = self.writeBuffer.find("\r\n")
        if end >= 0:
            if self.state == 0:
                line, self.writeBuffer = self.writeBuffer[:end], self.writeBuffer[end:]
                w = line.split(" ")
                if (w[0] != "protocol") or (len(w) != 2) or (w[1] not in self.supported):
                    self.readBuffer += "not-supported\r\n"
                else:
                    self.readBuffer += "protocol %s\r\n" % w[1]
                    self.state += 1

class ServerSocket(object):
    def __init__(self, supportedList):
        self.supported = supportedList
        self.readBuffer = ""
        self.writeBuffer = ""
        self.state = 0
        self.choice = None
    
    def read(self, count):
        if count <= len(self.readBuffer):
            data, self.readBuffer = self.readBuffer[:count], self.readBuffer[count:]
            return data
        else:
            raise EOFError("Read would have blocked forever")
    
    def write(self, data):
        self.writeBuffer += data
        end = self.writeBuffer.find("\r\n")
        if end >= 0:
            if self.state == 0:    
                line, self.writeBuffer = self.writeBuffer[:end], self.writeBuffer[end:]
                w = line.split(" ")
                matches = [name for name in w[1:] if name in self.supported]
                if (w[0] != "supports") or (len(w) < 2) or (len(matches) == 0):
                    self.readBuffer += "not-supported\r\n"
                else:
                    self.choice = matches[0]
                    self.readBuffer += "protocol %s\r\n" % self.choice
                    self.state += 1
            elif self.state == 1:
                line, self.writeBuffer = self.writeBuffer[:end], self.writeBuffer[end:]
                w = line.split(" ")
                if (w[0] != "protocol") or (len(w) != 2) or (w[1] != self.choice):
                    self.readBuffer += "not-supported\r\n"
                else:
                    self.readBuffer += "protocol %s\r\n" % w[1]
                    self.state += 1

class ProtocolNegociationTest(unittest.TestCase):
    def testServerNegociationSupported(self):
        """ Negociation should work out if there is at last one supported protocol. """
        supported = ["SPARKv2", "SPARKv1"]
        f = ClientSocket(supported)
        name = negociateProtocol(f, False)
        self.assertTrue(name in supported)
    
    def testServerNegociationNotSupported(self):
        """ Negociation should not work out if there is no supported protocol. """
        supported = ["SPARKv2"]
        f = ClientSocket(supported)
        try:
            name = negociateProtocol(f, False)
            self.fail("Protocol negociation should have failed, no supported protocol")
        except:
            pass

    def testClientNegociationSupported(self):
        """ Negociation should work out if there is at last one supported protocol. """
        supported = ["SPARKv2", "SPARKv1"]
        f = ServerSocket(supported)
        name = negociateProtocol(f, True)
        self.assertTrue(name in supported)
    
    def testClientNegociationNotSupported(self):
        """ Negociation should not work out if there is no supported protocol. """
        supported = ["SPARKv2"]
        f = ServerSocket(supported)
        try:
            name = negociateProtocol(f, True)
            self.fail("Protocol negociation should have failed, no supported protocol")
        except:
            pass

if __name__ == '__main__':
    unittest.main()