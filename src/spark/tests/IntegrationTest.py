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
from spark.async import Future
from spark.messaging.messages import *
from spark.fileshare import FileShare

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4550

class BasicIntegrationTest(unittest.TestCase):
    def test(self):
        """ Two locally-connected file shares should be able to exchange their file lists. """
        listenCalled = Future()
        serverDone = Future()
        serverThread = threading.Thread(target=self.server, args=(listenCalled, serverDone))
        serverThread.daemon = True
        serverThread.start()
        listenCalled.wait(1.0)
        clientDone = Future()
        clientThread = threading.Thread(target=self.client, args=(clientDone, ))
        clientThread.daemon = True
        clientThread.start()
        response = clientDone.wait(1.0)[0]
        serverDone.wait(1.0)
        self.assertTrue(isinstance(response, dict))
        self.assertEqual(0, len(response))
    
    def client(self, cont):
        try:
            remoteAddr = (BIND_ADDRESS, BIND_PORT)
            s = FileShare()
            s.startThread()
            s.connect(remoteAddr).wait(1.0)
            response = s.files().wait(1.0)[0]
            s.disconnect().wait(1.0)
            cont.completed(response)
        except:
            cont.failed()
    
    def server(self, listenCont, discCont):
        try:
            s = FileShare()
            s.startThread()
            cont = s.listen(("", 4550))
            listenCont.completed()
            cont.wait(1.0)[0]
            s.join().wait(1.0)
            discCont.completed()
        except:
            if listenCont.pending:
                listenCont.failed()
            discCont.failed()

if __name__ == '__main__':
    import sys
    unittest.main(argv=sys.argv)