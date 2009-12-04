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
from spark.messaging import TcpTransport, MessagingSession, Service
from spark.fileshare import FileShare
from spark.tests.AioTest import runReactorTypes, PipeTransport, PipeWrapper

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4550

class TestService(Service):
    def __init__(self, session, name=None):
        super(TestService, self).__init__(session, name)
        session.registerService(self)
    
    def foo(self):
        return self.session.sendRequest(Request("foo"))
    
    def requestFoo(self, req):
        """ The remote peer sent a 'foo' request. """
        return {'foo': 'bar'}

class BasicIntegrationTest(unittest.TestCase):
    @runReactorTypes
    def testTcpSession(self, reactorType):
        """ Two services connected by TCP/IP sockets should be able to exchange messages. """
        rea = reactorType("reactor")
        rea.launch_thread()
        response = self.beginTestTcpSession(rea).wait(1.0)
        rea.close()
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(1, len(response))
        self.assertEqual("bar", response["foo"])
    
    @runReactorTypes
    def testPipeSession(self, reactorType):
        """ Two services connected by pipes should be able to exchange messages. """
        rea = reactorType("reactor")
        rea.launch_thread()
        response = self.beginTestPipeSession(rea).wait(1.0)
        rea.close()
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(1, len(response))
        self.assertEqual("bar", response["foo"])
    
    @coroutine
    def beginTestTcpSession(self, rea):
        clientTransport = TcpTransport(rea, "client")
        serverTransport = TcpTransport(rea, "server")
        clientSession = MessagingSession(clientTransport, "client")
        serverSession = MessagingSession(serverTransport, "server")
        clientService = TestService(clientSession, "client")
        serverService = TestService(serverSession, "server")
        serverTransport.listen((BIND_ADDRESS, BIND_PORT))
        yield clientTransport.connect((BIND_ADDRESS, BIND_PORT))
        yield clientSession.waitActive()
        response = yield clientService.foo()
        yield clientTransport.disconnect()
        yield response.params
    
    @coroutine
    def beginTestPipeSession(self, rea):
        r1, w1 = rea.pipe()
        r2, w2 = rea.pipe()
        p1 = PipeWrapper(r1, w2)
        p2 = PipeWrapper(r2, w1)
        clientTransport = PipeTransport(rea, p1, "client")
        serverTransport = PipeTransport(rea, p2, "server")
        clientSession = MessagingSession(clientTransport, "client")
        serverSession = MessagingSession(serverTransport, "server")
        clientService = TestService(clientSession, "client")
        serverService = TestService(serverSession, "server")
        serverTransport.listen(None)
        yield clientTransport.connect(None)
        yield clientSession.waitActive()
        response = yield clientService.foo()
        yield clientTransport.disconnect()
        yield response.params

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=5)
    b = BasicIntegrationTest("testPipeSession")
    b.testPipeSession()
    #import sys
    #unittest.main(argv=sys.argv)