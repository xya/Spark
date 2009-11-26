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
import os
from spark.async import Future, PollReactor

TestFile = os.path.join(os.path.dirname(__file__), 'ProtocolTest.log')

class ReactorTest(unittest.TestCase):
    def testAsyncRead(self):
        """ beginRead() should be able to read from a file. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        with PollReactor() as rea:
            rea.launch_thread()
            with rea.open(TestFile) as file:
                f = file.beginRead(19)
                f.after(read_complete)
                f.wait(1.0)
                # TODO: make it thread-safe
                self.assertEqual(1, len(results))
                self.assertEqual("0023 > list-files 0", results[0])
    
    def testAsyncPipe(self):
        """ beginRead() should be able to read what was written on a pipe. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        with PollReactor() as rea:
            r, w = rea.pipe()
            try:
                rea.launch_thread()
                f = r.beginRead(3)
                f.after(read_complete)
                w.write("foo")
                f.wait(1.0)
                # TODO: make it thread-safe
                self.assertEqual(1, len(results))
                self.assertEqual("foo", results[0])
            finally:
                r.close()
                w.close()

if __name__ == '__main__':
    import sys
    unittest.main(argv=sys.argv)