#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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
import os
import unittest
from unittest import TestCase, TestLoader, TestSuite
import logging
from spark.core import *
from spark.messaging import *

class CustomLoader(TestLoader):
    def loadTestsFromTestCase(self, testCaseClass):
        return super(CustomLoader, self).loadTestsFromTestCase(testCaseClass)

def run_tests(modules=None, level=logging.ERROR):
    import locale
    locale.setlocale(locale.LC_ALL, '')
    if "-v" in sys.argv:
        verbosity = 2
    else:
        verbosity = 1
    logging.basicConfig(level=level)
    loader = CustomLoader()
    if modules is None:
        modules = ["__main__"]
    moduleTests = [loader.loadTestsFromName(m) for m in modules]
    unittest.TextTestRunner(verbosity=verbosity).run(TestSuite(moduleTests))

def processTimeout(timeout):
    """
    Decorator that runs the callable in a new process. It eventually returns
    the callable's return value or raise an exception if its execution takes too long.
    """
    def decorator(fun):
        def wrapper(*args, **kw):
            cont = Future()
            pid = Process.spawn(cont.run, (fun, ) + args, "TimeoutProcess")
            try:
                return cont.wait(timeout)
            except WaitTimeoutError:
                Process.kill(pid)
                raise
        return wrapper
    return decorator

def assertMatch(pattern, o):
    if not match(pattern, o):
        raise AssertionError("Object %s should match the pattern %s, but doesn't"
            % (repr(o), repr(pattern)))

def assertNoMatch(pattern, o):
    if match(pattern, o):
        raise AssertionError("Object %s should not match the pattern %s, but does"
            % (repr(o), repr(pattern)))

def testFilePath(fileName):
    return os.path.join(os.path.dirname(__file__), fileName)