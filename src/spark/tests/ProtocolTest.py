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
import sys
import os
from spark.async import Future, TaskFailedError, coroutine, process
from spark.messaging import *
from spark.tests.common import run_tests, processTimeout
from StringIO import StringIO

TestFile = os.path.join(os.path.dirname(__file__), 'ProtocolTest.log')
TestText = """0023 > list-files 0 {"register": true}
007d < list-files 0 {"<guid>": {"id": "<guid>", "last-modified": "20090619T173529.000Z", "name": "Report.pdf", "size": 3145728}}
007c ! file-added 55 {"id": "<guid>", "last-modified": "20090619T173529.000Z", "name": "SeisRoX-2.0.9660.exe", "size": 3145728}
0066 > create-transfer 26 {"blocksize": 1024, "file-id": "<guid>", "ranges": [{"end": 3071, "start": 0}]}
0036 < create-transfer 26 {"id": 2, "state": "inactive"}
001f > start-transfer 27 {"id": 2}
0034 < start-transfer 27 {"id": 2, "state": "starting"}
003a ! transfer-state-changed 56 {"id": 2, "state": "active"}
0018 \x00\x01\x00\x02\x00\x00\x00\x00\x00\x0cHello, world
0018 \x00\x01\x00\x02\x00\x00\x00\x01\x00\x0cSpaces      
040c \x00\x01\x00\x02\x00\x00\x0b\xff\x04\x00""" + ("!" * 1024) + """
001f > close-transfer 28 {"id": 2}
001e < close-transfer 28 {"id": 2}"""

TestItems = [
    Request("list-files", {"register": True}, 0),
    Response("list-files", {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}, 0),
    Notification("file-added", {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}, 55),
    Request("create-transfer", {"file-id": "<guid>", "blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}, 26),
    Response("create-transfer", {"id": 2, "state": "inactive"}, 26),
    Request("start-transfer", {"id": 2}, 27),
    Response("start-transfer", {"id": 2, "state": "starting"}, 27),
    Notification("transfer-state-changed", {"id": 2, "state": "active"}, 56),
    Block(2, 0, "Hello, world"),
    Block(2, 1, "Spaces      "),
    Block(2, 3071, "!" * 1024),
    Request("close-transfer", {"id": 2}, 28),
    Response("close-transfer", {"id": 2}, 28),
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
    
    def readAllMessages(self, reader):
        messages = []
        while True:
            message = reader.read()
            if message is not None:
                messages.append(message)
            else:
                return messages
    
    def testParseTextString(self):
        """ Ensure that messageReader() can read messages from a text string """
        p = messageReader(StringIO(TestText))
        actualItems = self.readAllMessages(p)
        self.assertSeqsEqual(TestItems, actualItems)
    
    def testParseTextFile(self):
        """ Ensure that messageReader() can read messages from a text file """
        with open(TestFile, "r") as f:
            p = messageReader(f)
            actualItems = self.readAllMessages(p)
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
        f =  StringIO()
        writer = messageWriter(f)
        for item in TestItems:
            writer.write(item)
        f.seek(0)
        actualItems = self.readAllMessages(messageReader(f))
        self.assertSeqsEqual(TestItems, actualItems)

def formatMessage(m):
    data = " %s\r\n" % str(m)
    return "%04x%s" % (len(data), data)

class Pipe(object):
    def __init__(self, readFD, writeFD):
        self.readFD = readFD
        self.writeFD = writeFD
    
    def read(self, size):
        return os.read(self.readFD, size)
    
    def write(self, data):
        os.write(self.writeFD, data)
    
    @classmethod
    def create(cls):
        r1, w1 = os.pipe()
        r2, w2 = os.pipe()
        return (cls(r1, w2), cls(r2, w1))

class MockFile(object):
    def __init__(self):
        self.readBuffer = ""
        self.writeBuffer = ""
    
    def read(self, count):
        if (count is None) or (count <= 0):
            count = len(self.readBuffer)
        if count <= len(self.readBuffer):
            data, self.readBuffer = self.readBuffer[:count], self.readBuffer[count:]
            return data
        else:
            raise EOFError("Read would have blocked forever")
    
    def write(self, data):
        self.writeBuffer += data
        message = self.innerReadMessage()
        if message is not None:
            self.onMessageWritten(message)
    
    def innerWrite(self, data):
        """ Append data to the read buffer. """
        self.readBuffer += data
    
    def innerRead(self, size):
        """ Remove data from the write buffer. """
        data, self.writeBuffer = self.writeBuffer[:size], self.writeBuffer[size:]
        return data
    
    def innerReadMessage(self):
        bufferSize = len(self.writeBuffer)
        if bufferSize >= 4:
            messageSize = int(self.writeBuffer[0:4], 16)
            if bufferSize >= (4 + messageSize):
                self.innerRead(4)
                return self.innerRead(messageSize).strip()
        return None

class ClientSocket(MockFile):
    def __init__(self, supportedList):
        super(ClientSocket, self).__init__()
        self.supported = supportedList
        self.innerWrite(formatMessage("supports %s" % " ".join(supportedList)))
        self.state = 0
    
    def onMessageWritten(self, message):
        if self.state == 0:
            w = message.split(" ")
            if (w[0] != "protocol") or (len(w) != 2) or (w[1] not in self.supported):
                self.innerWrite(formatMessage("not-supported"))
            else:
                self.innerWrite(formatMessage("protocol %s" % w[1]))
                self.state += 1

class ServerSocket(MockFile):
    def __init__(self, supportedList):
        super(ServerSocket, self).__init__()
        self.supported = supportedList
        self.state = 0
        self.choice = None
    
    def onMessageWritten(self, message):
        if self.state == 0:
            w = message.split(" ")
            matches = [name for name in w[1:] if name in self.supported]
            if (w[0] != "supports") or (len(w) < 2) or (len(matches) == 0):
                self.innerWrite(formatMessage("not-supported"))
            else:
                self.choice = matches[0]
                self.innerWrite(formatMessage("protocol %s" % self.choice))
                self.state += 1
        elif self.state == 1:
            w = message.split(" ")
            if (w[0] != "protocol") or (len(w) != 2) or (w[1] != self.choice):
                self.innerWrite(formatMessage("not-supported"))
            else:
                self.innerWrite(formatMessage("protocol %s" % w[1]))
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
        except TaskFailedError as e:
            type, val, tb = e.inner()
            if type != NegociationError:
                raise
        except NegociationError:
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
        except NegociationError:
            pass
        except TaskFailedError as e:
            type, val, tb = e.inner()
            if type != NegociationError:
                raise
    
    @processTimeout(1.0)
    def testClientServerNegociation(self):
        """ Negociation should work out with client and server using the same negociation code. """
        pid = process.current()
        c, s = Pipe.create()
        def server():
            name = negociateProtocol(s, False)
            process.send(pid, name)
        def client():
            name = negociateProtocol(c, True)
            process.send(pid, name)
        process.spawn(server)
        process.spawn(client)
        firstName = process.receive()
        secondName = process.receive()
        for name in (firstName, secondName):
            self.assertTrue(name in Supported)
        self.assertEqual(firstName, secondName)

if __name__ == '__main__':
    import logging
    run_tests(level=logging.INFO)