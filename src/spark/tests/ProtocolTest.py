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
from spark.protocol import parser, writer
from spark.protocol import SupportedProtocolNames, ProtocolName, TextMessage, Blob, Block
from StringIO import StringIO

TestText = """supports SPARKv1
protocol SPARKv1
protocol SPARKv1
> list-files 0 18 {"register": true}
< list-files 0 108 {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}
! file-added 55 106 {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}
> create-transfer 26 58 {"blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}
< create-transfer 26 31 {"id": 1, "state": "unstarted"}
> start-transfer 27 9 {"id": 1}
< start-transfer 27 30 {"id": 1, "state": "starting"}
! transfer-state 56 28 {"id": 1, "state": "active"}
0x0014\x00\x01\x00\x02\x00\x00\x00\x00Hello, world
0x0408\x00\x01\x00\x02\x00\x00\x0B\xFF""" + ("!" * 1024)

TestItems = [
    SupportedProtocolNames(["SPARKv1"]),
    ProtocolName("SPARKv1"),
    ProtocolName("SPARKv1"),
    TextMessage(TextMessage.REQUEST, "list-files", 0, {"register": True}),
    TextMessage(TextMessage.RESPONSE, "list-files", 0, {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}),
    TextMessage(TextMessage.NOTIFICATION, "file-added", 55, {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}),
    TextMessage(TextMessage.REQUEST, "create-transfer", 26, {"blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}),
    TextMessage(TextMessage.RESPONSE, "create-transfer", 26, {"id": 1, "state": "unstarted"}),
    TextMessage(TextMessage.REQUEST, "start-transfer", 27, {"id": 1}),
    TextMessage(TextMessage.RESPONSE, "start-transfer", 27, {"id": 1, "state": "starting"}),
    TextMessage(TextMessage.NOTIFICATION, "transfer-state", 56, {"id": 1, "state": "active"}),
    Block(2, 0, "Hello, world"),
    Block(2, 3071, "!" * 1024),
]

class ProtocolTest(unittest.TestCase):
    def getTestItems(self):
        return TestItems
    
    def assertMessagesEqual(self, expected, actual):
        if expected is None:
            self.assertEqual(expected, actual)
        else:
            self.assertEqual(str(expected), str(actual))
    
    def __neq__(self, other):
        return not (self == other)
        
    def testParseProtocol(self):
        f = StringIO(TestText)
        p = parser(f)
        items = list(p.readAll())
        self.assertEqual(13, len(items))
    
    def testReadWriteSync(self):
        """ Ensure that messages written by writer() can be read by parser() """
        # first individual messages
        testItems = self.getTestItems()
        for item in testItems:
            self.readWriteSync(item)
        
        # then a stream of messages
        f = StringIO()
        w = writer(f)
        w.writeAll(testItems)
        f.seek(0)
        p = parser(f)
        actualItems = list(p.readAll())
        self.assertEqual(len(testItems), len(actualItems))
        for expected, actual in zip(testItems, actualItems):
            self.assertMessagesEqual(expected, actual)
    
    def readWriteSync(self, item):
        f = StringIO()
        w = writer(f)
        w.write(item)
        f.seek(0)
        p = parser(f)
        self.assertMessagesEqual(item, p.read())

if __name__ == '__main__':
    unittest.main()