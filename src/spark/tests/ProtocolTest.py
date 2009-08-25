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
    SupportedProtocolNames(["SPARKv1"]),
    ProtocolName("SPARKv1"),
    ProtocolName("SPARKv1"),
    TextMessage(TextMessage.REQUEST, "list-files", 0, {"register": True}),
    TextMessage(TextMessage.RESPONSE, "list-files", 0, {"<guid>": {"id": "<guid>", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}),
    TextMessage(TextMessage.NOTIFICATION, "file-added", 55, {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}),
    TextMessage(TextMessage.REQUEST, "create-transfer", 26, {"file-id": "<guid>", "blocksize": 1024, "ranges": [{"start": 0, "end": 3071}]}),
    TextMessage(TextMessage.RESPONSE, "create-transfer", 26, {"id": 2, "state": "inactive"}),
    TextMessage(TextMessage.REQUEST, "start-transfer", 27, {"id": 2}),
    TextMessage(TextMessage.RESPONSE, "start-transfer", 27, {"id": 2, "state": "starting"}),
    TextMessage(TextMessage.NOTIFICATION, "transfer-state-changed", 56, {"id": 2, "state": "active"}),
    Block(2, 0, "Hello, world"),
    Block(2, 3071, "!" * 1024),
    TextMessage(TextMessage.REQUEST, "close-transfer", 28, {"id": 2}),
    TextMessage(TextMessage.RESPONSE, "close-transfer", 28, {"id": 2}),
]

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
        """ Ensure that parser() can read messages from a text file """
        p = parser(StringIO(TestText))
        actualItems = list(p.readAll())
        self.assertSeqsEqual(TestItems, actualItems)
    
    def testReadWriteSync(self):
        """ Ensure that messages written by writer() can be read by parser() """
        # first individual messages
        for item in TestItems:
            f = StringIO()
            writer(f).write(item)
            f.seek(0)
            actual = parser(f).read()
            self.assertMessagesEqual(item, actual)
        
        # then a stream of messages
        f = StringIO()
        writer(f).writeAll(TestItems)
        f.seek(0)
        actualItems = list(parser(f).readAll())
        self.assertSeqsEqual(TestItems, actualItems)

if __name__ == '__main__':
    unittest.main()