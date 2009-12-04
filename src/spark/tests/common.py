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
from unittest import TestCase, TestLoader, TestSuite
import logging
from spark.async import Reactor

class ReactorTestBase(TestCase):
    def __init__(self, reactorType, methodName):
        super(ReactorTestBase, self).__init__(methodName)
        self.reactorType = reactorType
    
    def setUp(self):
        self.reactor = self.reactorType()
        self.reactor.launch_thread()
    
    def tearDown(self):
        self.reactor.close()
    
    def shortDescription(self):
        return "[%s] %s" % (self.reactorType.__name__,
            super(ReactorTestBase, self).shortDescription())

class CustomLoader(TestLoader):
    def loadTestsFromTestCase(self, testCaseClass):
        if issubclass(testCaseClass, ReactorTestBase):
            for reactorType in Reactor.available():
                return loadReactorTests(reactorType, testCaseClass)
        else:
            return super(CustomLoader, self).loadTestsFromTestCase(testCaseClass)

def loadReactorTests(reactorType, testClass):
    return TestSuite(testClass(reactorType, testName)
                    for testName in dir(testClass)
                    if testName.startswith("test"))

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