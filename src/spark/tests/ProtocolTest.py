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
from spark.protocol import *
from StringIO import StringIO

ExchangeText = """supports SPARKv1
protocol SPARKv1
protocol SPARKv1
> list-files 0 {"register" : true}
< list-files 0 {"<guid>" : {"id" : "<guid>", "name" : "Report.pdf", "size" : 3145728, "last-modified" : "20090619T173529.000Z"}}
! file-added 55 {"id" : "<guid>", "name" : "SeisRoX-2.0.9660.exe", "size" : 3145728, "last-modified" : "20090619T173529.000Z"}
> create-transfer 26 {"blocksize" : 1024, "ranges" : [{"start" : 0, "end" : 3071}]}
< create-transfer 26 {"id" : 1, "state" : "unstarted"}
> start-transfer 27 {"id" : 1}
< start-transfer 27 {"id" : 1, "state" : "starting"}
! transfer-state 56 {"id" : 1, "state" : "active"}
0x00000bhello world
0x00000bhello world"""

class ProtocolTest(unittest.TestCase):
    def testParseProtocol(self):
        f = StringIO(ExchangeText)
        p = parser(f)
        items = list(p.readAll())
        self.assertEqual(13, len(items))

if __name__ == '__main__':
    unittest.main()