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
from spark.async import Future, TaskError, asyncMethod

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
        except TaskError:
            pass
    
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

@asyncMethod
def foo(arg, future):
    future.completed("foo", arg)

class AsyncMethodTest(unittest.TestCase):
    def setUp(self):
        self.result = None
        
    def testSyncCall(self):
        """ Passing no future should invoke the method synchronously """
        result = foo("bar", None)
        self.assertEqual(("foo", "bar"), result)
    
    def testAsyncCall(self):
        """ Passing a future should invoke the method asynchronously """
        future = Future()
        foo("bar", future)
        future.wait()
        self.assertFalse(future.pending)
        self.assertEqual(("foo", "bar"), future.result)
    
    def testAsyncCallback(self):
        """ Passing a callable instead of a future should work as expected """
        foo("bar", self.futureCompleted)
        self.assertEqual(("foo", "bar"), self.result)
    
    def futureCompleted(self, future):
        self.result = future.result

if __name__ == '__main__':
    unittest.main()