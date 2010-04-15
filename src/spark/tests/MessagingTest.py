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
from spark.messaging import *
from spark.async import Future, Event
from spark.tests.common import run_tests, assertMatch, assertNoMatch
from spark.tests.ProtocolTest import testRequest, testResponse, testNotification, testBlock

class MessageMatchingTest(unittest.TestCase):
    def testString(self):
        """ match() should properly match string patterns """
        assertMatch("foo", "foo")
        assertNoMatch("foo", "bar")
    
    def testTuples(self):
        """ match() should properly match tuple patterns """
        assertMatch(("foo", int), ("foo", 1))
        assertNoMatch(("foo", int), ("bar", 1))
    
    def testMessages(self):
        """ match() should properly match message patterns """
        assertMatch(Request("swap", str, str), Request("swap", "foo", "bar").withID(1))
        assertMatch(Event("listening", None), Event('listening', ('127.0.0.1', 4550)))
        assertMatch(Block, Block(0, 1, 'foo'))
        assertNoMatch(Request("paws"), Request("swap", "foo", "bar").withID(1))
        assertNoMatch(Request("swap", "foo", "bar").withID(1), Request("swap"))
        assertNoMatch(('disconnect', ), Event("protocol-negociated", "SPARKv1"))
    
    def testMatchSubclass(self):
        """ match()  should match a type if it is one of its parent types """
        assertMatch(basestring, u"foo")

if __name__ == '__main__':
    run_tests()