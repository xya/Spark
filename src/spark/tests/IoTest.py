#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Pierre-André Saulais <pasaulais@free.fr>
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
from gnutls.crypto import OpenPGPCertificate, OpenPGPPrivateKey
from gnutls.connection import OpenPGPCredentials
from spark.core import *
from spark.messaging import *
from spark.tests.common import run_tests, processTimeout, assertMatch, testFilePath

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4559

class TestTcpSocket(TcpSocket):
    def __init__(self, receiverClass):
        super(TestTcpSocket, self).__init__()
        self.receiverClass = receiverClass
    
    def send(self, data):
        Process.send(self.pid, Command("send", data))
    
    def doSend(self, m, data, state):
        state.conn.send(data)
    
    def initPatterns(self, loop, state):
        super(TestTcpSocket, self).initPatterns(loop, state)
        loop.addHandlers(self, Command("send", basestring))
    
    def createReceiver(self, state):
        return self.receiverClass()

class NotifierTcpReceiver(TcpReceiver):
    def onConnected(self, m, state):
        p = state.conn.recv(128)
        while len(p) > 0:
            Process.send(state.senderPid, Event("packet-received", p))
            p = state.conn.recv(128)
        Process.exit()

class EchoTcpReceiver(TcpReceiver):
    def onConnected(self, m, state):
        p = state.conn.recv(128)
        while len(p) > 0:
            state.conn.send(p)
            p = state.conn.recv(128)
        Process.exit()
    
class TcpIoTest(unittest.TestCase):
    @processTimeout(1.0)
    def testConection(self):
        server = TestTcpSocket(EchoTcpReceiver)
        client = TestTcpSocket(NotifierTcpReceiver)
        with server:
            server.listen((BIND_ADDRESS, BIND_PORT))
            server.accept()
            with client:
                client.connected.suscribe()
                client.disconnected.suscribe()
                client.connect((BIND_ADDRESS, BIND_PORT))
                assertMatch(client.connected.pattern, Process.receive())
                client.send("foo")
                assertMatch(Event("packet-received", "foo"), Process.receive())
                client.disconnect()
                assertMatch(client.disconnected.pattern, Process.receive())

class TestSecureTcpSocket(SecureTcpSocket):
    def __init__(self, receiverClass, cert_path, key_path):
        self.receiverClass = receiverClass
        cert = OpenPGPCertificate(open(testFilePath(cert_path)).read())
        key = OpenPGPPrivateKey(open(testFilePath(key_path)).read())
        super(TestSecureTcpSocket, self).__init__(cert, key)
    
    def send(self, data):
        Process.send(self.pid, Command("send", data))
    
    def doSend(self, m, data, state):
        state.conn.send(data)
    
    def initPatterns(self, loop, state):
        super(TestSecureTcpSocket, self).initPatterns(loop, state)
        loop.addHandlers(self, Command("send", basestring))
    
    def createReceiver(self, state):
        return self.receiverClass(state.cred)

class ClientSecureTcpReceiver(SecureTcpReceiver):
    def onSessionStarted(self, m, state):
        p = state.conn.recv(128)
        while len(p) > 0:
            Process.send(state.senderPid, Event("packet-received", p))
            p = state.conn.recv(128)
        Process.exit()

class ServerSecureTcpReceiver(SecureTcpReceiver):
    def onSessionStarted(self, m, state):
        p = state.conn.recv(128)
        while len(p) > 0:
            state.conn.send(p)
            p = state.conn.recv(128)
        Process.exit()

class SecureTcpIoTest(unittest.TestCase):
    @processTimeout(2.0)
    def testSecureConnection(self):
        with TestSecureTcpSocket(ServerSecureTcpReceiver, 'barney.pub.gpg', 'barney.priv.gpg') as server:
            server.listening.suscribe()
            server.connected.suscribe()
            server.certificateReceived.suscribe()
            server.disconnected.suscribe()
            server.listen((BIND_ADDRESS, BIND_PORT))
            assertMatch(server.listening.pattern, Process.receive())
            server.accept()
            Process.spawn_linked(self.startClient, name="testSecureConnectionClient")
            assertMatch(server.connected.pattern, Process.receive())
            auth = Process.receive()
            assertMatch(Event("certificate-received", None), auth)
            peer_cert = auth[2]
            self.assertEqual("27fbcdf93820a93363987a1d6beca16cefaf6aa4", peer_cert.fingerprint)
            server.startSession()
            assertMatch(server.disconnected.pattern, Process.receive())
    
    def startClient(self):
        with TestSecureTcpSocket(ClientSecureTcpReceiver, 'alice.pub.gpg', 'alice.priv.gpg') as client:
            client.connected.suscribe()
            client.certificateReceived.suscribe()
            client.disconnected.suscribe()
            client.connect((BIND_ADDRESS, BIND_PORT))
            assertMatch(client.connected.pattern, Process.receive())
            auth = Process.receive()
            assertMatch(Event("certificate-received", None), auth)
            peer_cert = auth[2]
            self.assertEqual("b778501ce25e5fc894c8d93364a5d23253a4402", peer_cert.fingerprint)
            client.startSession()
            client.send("foo")
            assertMatch(Event("packet-received", "foo"), Process.receive())
            client.disconnect()
            assertMatch(client.disconnected.pattern, Process.receive())

if __name__ == '__main__':
    import logging
    from spark.core import debugger
    watch_pipe_name = "/tmp/spark_watcher_%s_%d" % (BIND_ADDRESS, BIND_PORT)
    debugger.start_watcher(watch_pipe_name)
    run_tests(level=logging.INFO)