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
from spark.async import Future, coroutine
from spark.messaging.messages import *
from spark.messaging import TcpTransport, MessagingSession
from spark.fileshare import FileShare
from spark.tests.AioTest import runReactorTypes, PipeTransport

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4550

class BasicIntegrationTest(unittest.TestCase):
    @runReactorTypes
    def test(self, reactorType):
        """ Two locally-connected file shares should be able to exchange their file lists. """
        rea = reactorType("reactor")
        rea.launch_thread()
        response = self.beginTest(rea).wait(1.0)
        rea.close()
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(1, len(response))
    
    @coroutine
    def beginTest(self, rea):
        clientTransport = TcpTransport(rea, "client")
        serverTransport = TcpTransport(rea, "server")
        clientSession = MessagingSession(clientTransport, "client")
        serverSession = MessagingSession(serverTransport, "server")
        clientShare = FileShare(clientSession, "client")
        serverShare = FileShare(serverSession, "server")
        serverTransport.listen((BIND_ADDRESS, BIND_PORT))
        yield clientTransport.connect((BIND_ADDRESS, BIND_PORT))
        response = yield rea.send(clientShare.files)
        time.sleep(0.1) # temporary hack until I start testing a *real* request that sends a message 
        yield clientTransport.disconnect()
        yield response

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=5)
    b = BasicIntegrationTest("test")
    b.test()
    #import sys
    #unittest.main(argv=sys.argv)