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

class ReactorTest(unittest.TestCase):
    def testAsyncRead(self):
        results = []
        def read_complete(prev):
            results.append(prev.result)
        r, w = os.pipe()
        rea = PollReactor()
        try:
            rea.launch_thread()
            rea.register(r)
            f = rea.read(r, 3)
            f.after(read_complete)
            os.write(w, "foo")
            f.wait(1.0)
            # TODO: make it thread-safe
            self.assertEqual(1, len(results))
            self.assertEqual("foo", results[0])
        finally:
            rea.close()
            os.close(r)
            os.close(w)

if __name__ == '__main__':
    import sys
    unittest.main(argv=sys.argv)