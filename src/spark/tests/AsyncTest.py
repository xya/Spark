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
from spark.async import Future, TaskError

class FutureTest(unittest.TestCase):
    def testCompleted(self):
        f = Future()
        self.assertTrue(f.pending)
        f.completed("spam", "eggs")
        self.assertFalse(f.pending)
        self.assertEqual(("spam", "eggs"), f.results)
        self.assertEqual("spam", f.result)
    
    def testFailedSimple(self):
        f = Future()
        self.assertTrue(f.pending)
        f.failed()
        self.assertFalse(f.pending)
        try:
            r = f.results
            self.fail("results didn't raise an exception")
        except:
            pass
    
    def testFailedException(self):
        f = Future()
        try:
            raise KeyError("The key was not found")
        except:
            f.failed()

        try:
            r = f.results
            self.fail("results didn't raise an exception")
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
    
    def testCallback(self):
        """ The callback should be invoked with the right arguments (result plus positional args). """
        result = []
        def bar(prev, *args):
            result.append(prev.results + args)
        f = Future()
        f.after(bar, 1, 2, 3)
        f.completed("spam", "eggs")
        self.assertEqual(1, len(result))
        self.assertEqual(("spam", "eggs", 1, 2, 3), result[0])
    
    def testAfterCompleted(self):
        """ The callback should be invoked even when after() is called after completion. """
        result = []
        def bar(prev, *args):
            result.append(prev.results + args)
        f = Future()
        f.completed("spam", "eggs")
        f.after(bar, 1, 2, 3)
        self.assertEqual(1, len(result))
        self.assertEqual(("spam", "eggs", 1, 2, 3), result[0])
    
    def testBoundMethodCallback(self):
        """ Callbacks to bound methods should be usable as continuations. """
        class Foo(object):
            def __init__(self):
                self.result = []
            def bar(self, f):
                self.result.append(f.results)
        foo = Foo()
        f = Future()
        f.after(foo.bar)
        f.completed("spam", "eggs")
        self.assertEqual(1, len(foo.result))
        self.assertEqual(("spam", "eggs"), foo.result[0])
    
    def testForkOK(self):
        result = []
        error = []
        def bar(*args):
            result.append(args)
        def foo(*args):
            error.append(args)
        f = Future()
        f.fork(bar, foo, 1, 2, 3)
        f.completed("spam", "eggs")
        self.assertEqual(1, len(result))
        self.assertEqual(0, len(error))
        self.assertEqual(("spam", "eggs", 1, 2, 3), result[0])
        
        fOK, fFail, f2 = Future(), Future(), Future()
        f2.fork(fOK, fFail, 1, 2, 3)
        f2.completed("spam", "eggs")
        self.assertEqual(False, fOK.pending)
        self.assertEqual(True, fFail.pending)
        self.assertEqual(("spam", "eggs", 1, 2, 3), fOK.results)
    
    def testForkFail(self):
        result = []
        error = []
        def bar(*args):
            result.append(args)
        def foo(*args):
            error.append(args)
        f = Future()
        f.fork(bar, foo, 1, 2, 3)
        f.failed(KeyError())
        self.assertEqual(0, len(result))
        self.assertEqual(1, len(error))
        self.assertEqual((1, 2, 3), error[0])
        
        fOK, fFail, f2 = Future(), Future(), Future()
        f2.fork(fOK, fFail, 1, 2, 3)
        f2.failed(KeyError())
        self.assertEqual(True, fOK.pending)
        self.assertEqual(False, fFail.pending)
        try:
            fFail.wait()
            self.fail("wait should have thrown an exception")
        except:
            pass

if __name__ == '__main__':
    unittest.main()