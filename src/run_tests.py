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
import spark
from spark.tests import *

def loadModuleTests(module):
    ''' Returns every tests from a given module '''
    return unittest.defaultTestLoader.loadTestsFromModule(module)

def allModules():
    ''' Returns the modules to test '''
    for name in spark.tests.__all__:
        yield sys.modules['spark.tests.' + name]

def allTests():
    ''' Returns every test from every module '''
    return unittest.TestSuite(map(loadModuleTests, allModules()))

if __name__ == '__main__':
    import locale    
    locale.setlocale(locale.LC_ALL, '')
    if "-v" in sys.argv:
        verbosity = 2
    else:
        verbosity = 1
    unittest.TextTestRunner(verbosity=verbosity).run(allTests())