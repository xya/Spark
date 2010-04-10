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
from spark.async import Future, coroutine, process
from spark.messaging.messages import *
from spark.messaging import TcpTransport, PipeTransport, MessagingSession, Service
from spark.fileshare import FileShare
from spark.messaging.service import TcpMessenger
from spark.tests.common import ReactorTestBase, run_tests, processTimeout

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4550

class ProcessIntegrationTest(unittest.TestCase):
    def assertMatch(self, pattern, o):
        if not match(pattern, o):
            self.fail("Object doesn't match the pattern: '%s' (pattern: '%s')"
                % (repr(o), repr(pattern)))
    
    @processTimeout(1.0)
    def testTcpSession(self):
        # TODO: fix connection refused (connect is called before bind/listen/accept)
        log = process.logger()
        def serverLoop():
            log = process.logger()
            serverMessenger = TcpMessenger(process.current())
            serverMessenger.listen((BIND_ADDRESS, BIND_PORT))
            while True:
                m = process.receive()
                if match(Request("swap", (None, None)), m):
                    resp = Response("swap", (m.params[1], m.params[0]), m.transID)
                    serverMessenger.send(resp)
                else:
                    break
        process.spawn(serverLoop, name="ServerLoop")
        clientMessenger = TcpMessenger(process.current())
        clientMessenger.connect((BIND_ADDRESS, BIND_PORT))
        clientMessenger.send(Request("swap", ("foo", "bar"), 1))
        resp = process.receive()
        if(match(("connection-error", None), resp)):
            self.fail(str(resp[1]))
        self.assertMatch(Response("swap", ("bar", "foo"), 1), resp)
        clientMessenger.disconnect()

if __name__ == '__main__':
    import logging
    run_tests(level=logging.INFO)