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
from spark.async import Future

class FutureTest(unittest.TestCase):
    def testCompleted(self):
        f = Future()
        self.assertTrue(f.pending)
        f.completed("spam", "eggs")
        self.assertFalse(f.pending)
        self.assertEqual(("spam", "eggs"), f.result)
    
    def testFailedSimple(self):
        f = Future()
        self.assertTrue(f.pending)
        f.failed()
        self.assertFalse(f.pending)
        try:
            r = f.result
            self.fail("result didn't raise an exception")
        except:
            pass
    
    def testFailedException(self):
        f = Future()
        try:
            raise KeyError("The key was not found")
        except Exception, e:
            f.failed(e)

        try:
            r = f.result
            self.fail("result didn't raise an exception")
        except KeyError:
            pass
        except:
            self.fail("result didn't raise the right type of exception")
    
    def testCompletedTwice(self):
        f = Future()
        f.completed("spam", "eggs")
        try:
            f.completed("eggs", "spam")
            self.fail("completed() didn't raise an exception the second time")
        except:
            pass
        
        f = Future()
        f.failed()
        try:
            f.completed("eggs", "spam")
            self.fail("completed() didn't raise an exception after failed() was called")
        except:
            pass
    
    def testFailedTwice(self):
        f = Future()
        f.failed()
        try:
            f.failed()
            self.fail("failed() didn't raise an exception the second time")
        except:
            pass
        
        f = Future()
        f.completed("eggs", "spam")        
        try:
            f.failed()
            self.fail("failed() didn't raise an exception after completed() was called")
        except:
            pass
    
    def testBoundMethodCallback(self):
        class Foo(object):
            def __init__(self):
                self.result = []
            def bar(self, f):
                self.result.append(f.result)
        foo = Foo()
        f = Future(foo.bar)
        f.completed("spam", "eggs")
        self.assertEqual(1, len(foo.result))
        self.assertEqual(("spam", "eggs"), foo.result[0])

if __name__ == '__main__':
    unittest.main()