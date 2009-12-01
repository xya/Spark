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
import functools
import os
from spark.async import Future

Reactors = []

try:
    from spark.async.pollreactor import PollReactor
    Reactors.append(PollReactor)
except ImportError:
    pass
    
try:
    from spark.async.iocpreactor import CompletionPortReactor
    Reactors.append(CompletionPortReactor)
except ImportError:
    pass

TestFile = os.path.join(os.path.dirname(__file__), 'ProtocolTest.log')

def runReactors(testMethod):
    """ Run the test with all available reactors. """
    @functools.wraps(testMethod)
    def wrapper(self):
        for reactor in Reactors:
            with reactor() as rea:
                rea.launch_thread()
                testMethod(self, rea)
    return wrapper

def runReactorTypes(testMethod):
    """ Run the test with all available reactor types. """
    @functools.wraps(testMethod)
    def wrapper(self):
        for reactor in Reactors:
            testMethod(self, reactor)
    return wrapper

class ReactorTest(unittest.TestCase):
    @runReactors
    def testSend(self, rea):
        """ send() should invoke the callable asynchronously and return the result """
        def bar(arg):
            return (arg, "bar")
        result = rea.send(bar, "foo").wait(1.0)
        self.assertEqual(("foo", "bar"), result)
    
    @runReactors
    def testPost(self, rea):
        """ post() should invoke the callable asynchronously """
        cont = Future()
        def complete(arg1, arg2):
            cont.completed((arg1, arg2))
        rea.post(complete, "foo", "bar")
        result = cont.wait(1.0)
        self.assertEqual(("foo", "bar"), result)

    @runReactors
    def testAsyncRead(self, rea):
        """ beginRead() should be able to read from a file. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        with rea.open(TestFile) as file:
            f = file.beginRead(19)
            f.after(read_complete)
            f.wait(1.0)
            # TODO: make it thread-safe
            self.assertEqual(1, len(results))
            self.assertEqual("0023 > list-files 0", results[0])
    
    @runReactors
    def testAsyncPipe(self, rea):
        """ beginRead() should be able to read what was written on a pipe. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        r, w = rea.pipe()
        try:
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