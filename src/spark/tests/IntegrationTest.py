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
import threading
import functools
import time
from spark.async import *
from spark.messaging import *
from spark.tests.common import run_tests, processTimeout, assertMatch

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4559

class TestServer(Service):
    def __init__(self):
        super(TestServer, self).__init__()
        self.listening = EventSender("listening", None)
    
    def initPatterns(self, loop, state):
        super(TestServer, self).initPatterns(loop, state)
        loop.suscribeTo(state.messenger.listening, callable=self.handleListening)
        loop.suscribeTo(state.messenger.disconnected, result=False)
        loop.addHandler(Request("swap", basestring, basestring), self)
    
    def handleListening(self, m, state):
        self.listening(m)
    
    def requestSwap(self, req, transID, a, b, state):
        self.sendResponse(state, req, b, a)
    
class ProcessIntegrationTest(unittest.TestCase):
    @processTimeout(1.0)
    def testTcpSession(self):
        with TestServer() as server:
            server.listening.suscribe()
            Process.send(server.pid, Command("bind", (BIND_ADDRESS, BIND_PORT)))
            assertMatch(Event("listening", None), Process.receive())
            with TcpMessenger() as client:
                client.protocolNegociated.suscribe()
                client.disconnected.suscribe()
                client.connect((BIND_ADDRESS, BIND_PORT))
                assertMatch(Event("protocol-negociated", basestring), Process.receive())
                client.send(Request("swap", "foo", "bar").withID(1))
                assertMatch(Response("swap", "bar", "foo").withID(1), Process.receive())
            assertMatch(Event("disconnected"), Process.receive())

if __name__ == '__main__':
    import logging
    run_tests(level=logging.INFO)