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

from gnutls.connection import ClientSession, ServerSession, OpenPGPCredentials
from spark.core import *

__all__ = ["SecureTcpSocket", "SecureTcpReceiver"]

class SecureTcpSocket(TcpSocket):
    def __init__(self, cert, key):
        super(SecureTcpSocket, self).__init__()
        self.cert = cert
        self.key = key
        self.certificateReceived = EventSender("certificate-received", None)
    
    def startSession(self, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("start-session", senderPid))
        
    def initState(self, state):
        super(SecureTcpSocket, self).initState(state)
        state.cred = OpenPGPCredentials(self.cert, self.key)
        state.peer_cert = None
    
    def initPatterns(self, loop, state):
        super(SecureTcpSocket, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("start-session", int),
            Event("handshake-done", None))
    
    def closeConnection(self, state):
        try:
            if state.conn:
                try:
                    state.logger.info("Sending TLS 'bye' message")
                    state.conn.bye()
                except Exception:
                    pass
        finally:
            super(SecureTcpSocket, self).closeConnection(state)
    
    def createReceiver(self, state):
        return SecureTcpReceiver(state.cred)
    
    def onHandshakeDone(self, m, peer_cert, state):
        state.peer_cert = peer_cert
        state.logger.info("Connected to peer: " + unicode(state.peer_cert.name))
        self.certificateReceived(peer_cert)
    
    def doStartSession(self, m, senderPid, state):
        if not state.peer_cert:
            Process.send(senderPid, Event("session-error", "invalid-state"))
        Process.send(state.receiver, Event("session-started"))

class SecureTcpReceiver(TcpReceiver):
    def __init__(self, cred):
        super(SecureTcpReceiver, self).__init__()
        self.cred = cred
    
    def initState(self, state):
        super(SecureTcpReceiver, self).initState(state)
        state.cred = self.cred
    
    def initPatterns(self, loop, state):
        super(SecureTcpReceiver, self).initPatterns(loop, state)
        loop.addHandlers(self, Event("session-started"))
    
    def connectionEstablished(self, conn, remoteAddr, state):
        if state.initiating:
            session = ClientSession(conn, state.cred)
        else:
            session = ServerSession(conn, state.cred, True)
        super(SecureTcpReceiver, self).connectionEstablished(session, remoteAddr, state)
    
    def onConnected(self, m, state):
        state.conn.handshake()
        Process.send(state.messengerPid, Event("handshake-done", state.conn.peer_certificate))
    
    def onSessionStarted(self, m, state):
        pass