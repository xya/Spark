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
from spark.async import Future
from spark.messaging.messages import *
from spark.fileshare import FileShare
from spark.tests.AioTest import runReactorTypes

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4550

class BasicIntegrationTest(unittest.TestCase):
    @runReactorTypes
    def test(self, reactorType):
        """ Two locally-connected file shares should be able to exchange their file lists. """
        listenCalled = Future()
        serverDone = Future()
        serverThread = threading.Thread(target=self.server,
                                        args=(reactorType, listenCalled, serverDone))
        serverThread.daemon = True
        serverThread.start()
        listenCalled.wait(1.0)
        clientDone = Future()
        clientThread = threading.Thread(target=self.client, args=(reactorType, clientDone))
        clientThread.daemon = True
        clientThread.start()
        response = clientDone.wait(1.0)[0]
        serverDone.wait(1.0)
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(1, len(response))
    
    def client(self, reactorType, cont):
        try:
            remoteAddr = (BIND_ADDRESS, BIND_PORT)
            rea = reactorType("client")
            rea.launch_thread()
            s = FileShare(rea, "client")
            s.connect(remoteAddr).wait(1.0)
            response = s.files().wait(1.0)[0]
            s.disconnect().wait(1.0)
            cont.completed(response)
        except:
            cont.failed()
    
    def server(self, reactorType, listenCont, discCont):
        try:
            rea = reactorType("server")
            rea.launch_thread()
            s = FileShare(rea, "server")
            s.onDisconnected += discCont.completed
            s.listen(("", 4550))
            listenCont.completed()
        except:
            if listenCont.pending:
                listenCont.failed()
            discCont.failed()

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    b = BasicIntegrationTest("test")
    b.test()
    #import sys
    #unittest.main(argv=sys.argv)