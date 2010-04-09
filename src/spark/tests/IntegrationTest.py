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
    @processTimeout(1.0)
    def testTcpSession(self):
        serverMessenger = TcpMessenger()
        def serverLoop():
            serverMessenger.set_receiver(process.current())
            while True:
                m = process.receive()
                if match(m, ("swap", None, None)):
                    process.send(serverMessenger.pid, ("swapped", m[1], m[0]))
                else:
                    break
        process.spawn(serverLoop)
        clientMessenger = TcpMessenger()
        clientMessenger.set_receiver(process.current())
        serverMessenger.listen((BIND_ADDRESS, BIND_PORT))
        clientMessenger.connect((BIND_ADDRESS, BIND_PORT))
        clientMessenger.send(("swap", "foo", "bar"))
        self.assertTrue(match(process.receive(), ("connected", None)))
        self.assertTrue(match(process.receive(), ("protocol-negociated", None)))
        self.assertEqual(("swapped", "bar", "foo"), process.receive())

if __name__ == '__main__':
    import logging
    run_tests(level=logging.INFO)