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

import sys
import unittest
import functools
import os
import logging
from spark.async import Future, Reactor
from spark.messaging import Transport
from spark.tests.common import ReactorTestBase, run_tests

TestFile = os.path.join(os.path.dirname(__file__), 'ProtocolTest.log')

class ReactorTest(ReactorTestBase):
    def testSend(self):
        """ send() should invoke the callable asynchronously and return the result """
        def bar(arg):
            return (arg, "bar")
        result = self.reactor.send(bar, "foo").wait(1.0)
        self.assertEqual(("foo", "bar"), result)
    
    def testPost(self):
        """ post() should invoke the callable asynchronously """
        cont = Future()
        def complete(arg1, arg2):
            cont.completed((arg1, arg2))
        self.reactor.post(complete, "foo", "bar")
        result = cont.wait(1.0)
        self.assertEqual(("foo", "bar"), result)

    def testAsyncRead(self):
        """ beginRead() should be able to read from a file. """
        with self.reactor.open(TestFile) as file:
            result = file.beginRead(19).wait(1.0)
            self.assertEqual("0023 > list-files 0", result)
    
    def testAsyncPipe(self):
        """ beginRead() should be able to read what was written on a pipe. """
        r, w = self.reactor.pipe()
        try:
            f = r.beginRead(3)
            w.write("foo")
            result = f.wait(1.0)
            self.assertEqual("foo", result)
        finally:
            r.close()
            w.close()

if __name__ == '__main__':
    run_tests()