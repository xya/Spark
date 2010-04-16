# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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

import os
import socket
from spark.core import *

__all__ = ["TcpSocket"]

class TcpSocket(ProcessBase):
    # The messenger is not connected to any peer.
    DISCONNECTED = 0
    # The messenger is connected to a peer.
    CONNECTED = 1
    
    def __init__(self):
        super(TcpSocket, self).__init__()
        self.listening = EventSender("listening", None)
        self.connected = EventSender("connected", None)
        self.disconnected = EventSender("disconnected")
    
    def connect(self, addr, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("connect", addr, senderPid))
    
    def listen(self, addr, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("listen", addr, senderPid))
    
    def accept(self, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("accept", senderPid))
    
    def disconnect(self):
        Process.send(self.pid, Command("disconnect"))

    def initState(self, state):
        super(TcpSocket, self).initState(state)
        state.connState = TcpSocket.DISCONNECTED
        state.server = None
        state.conn = None
        state.remoteAddr = None
        state.receiver = None
        state.acceptReceiver = None
        state.connectReceiver = None
    
    def initPatterns(self, loop, state):
        super(TcpSocket, self).initPatterns(loop, state)
        loop.addHandlers(self,
            # public messages
            Command("connect", None, int),
            Command("listen", None, int),
            Command("accept", int),
            Command("disconnect"),
            # internal messages
            Event("connected", None, None, bool),
            Event("child-exited", int))
    
    def cleanup(self, state):
        try:
            self._closeConnection(state)
            self._closeServer(state)
        finally:
            super(TcpSocket, self).cleanup(state)
    
    def _childWrapper(self, fun):
        messengerPid = Process.current()
        def wrapper(*args):
            try:
                fun(*args)
            finally:
                Process.try_send(messengerPid, Event("child-exited", Process.current()))
        return wrapper
    
    def doListen(self, m, bindAddr, senderPid, state):
        if state.server:
            Process.send(senderPid, Event("listen-error", "invalid-state"))
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            state.logger.info("Listening to incoming connections on %s.", repr(m[2]))
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(bindAddr)
            server.listen(1)
            self.listening(bindAddr)
        except socket.error as e:
            state.logger.error("Error while listening: %s.", str(e))
            Process.send(senderPid, Event("listen-error", e))
        else:
            state.server = server
    
    def doAccept(self, m, senderPid, state):
        if state.acceptReceiver:
            # we are already waiting for an incoming connection
            return
        elif (state.connState != TcpSocket.DISCONNECTED) or not state.server:
            Process.send(senderPid, Event("accept-error", "invalid-state"))
            return
        entry = self._childWrapper(self._waitForAccept)
        args = (state.server, senderPid, Process.current())
        state.acceptReceiver = Process.spawn_linked(entry, args, "TcpServer")

    def _waitForAccept(self, server, senderPid, messengerPid):
        log = Process.logger()
        log.info("Waiting for a connection.")
        try:
            conn, remoteAddr = server.accept()
        except socket.error as e:
            if e.errno == os.errno.EINVAL:
                # shutdown
                return
            else:
                log.error("Error while accepting: %s.", str(e))
                Process.send(senderPid, Event("accept-error", e))
        else:
            self.childConfirmConnection(conn, remoteAddr, False, senderPid, messengerPid)

    def doConnect(self, m, remoteAddr, senderPid, state):
        if (state.connState != TcpSocket.DISCONNECTED) or state.connectReceiver:
            Process.send(senderPid, Event("connection-error", "invalid-state"))
            return
        entry = self._childWrapper(self._waitForConnect)
        args = (remoteAddr, senderPid, Process.current())
        state.connectReceiver = Process.spawn_linked(entry, args, "TcpClient")
    
    def _waitForConnect(self, remoteAddr, senderPid, messengerPid):
        log = Process.logger()
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        conn.bind(("0.0.0.0", 0))
        log.info("Connecting to %s.", repr(remoteAddr))
        try:
            conn.connect(remoteAddr)
        except socket.error as e:
            log.error("Error while connecting: %s.", str(e))
            Process.send(senderPid, Event("connection-error", e))
        else:
            self.childConfirmConnection(conn, remoteAddr, True, senderPid, messengerPid)

    def onConnected(self, m, conn, remoteAddr, initiating, state):
        if initiating:
            receiver = state.connectReceiver
        else:
            receiver = state.acceptReceiver
        if state.receiver:
            state.logger.info("Dropping redundant connection to %s.", repr(remoteAddr))
            Process.send(receiver, Command("close"))
        else:
            # we're connected, update the process' state
            state.logger.info("Connected to %s.", repr(remoteAddr))
            state.connState = TcpSocket.CONNECTED
            state.conn = conn
            state.remoteAddr = remoteAddr
            state.receiver = receiver
            Process.send(receiver, Command("connect"))
            self.connected(remoteAddr)
    
    def childConfirmConnection(self, conn, remoteAddr, initiating, senderPid, messengerPid):
        log = Process.logger()
        # notify the messenger process that we have established a connection
        Process.send(messengerPid, Event("connected", conn, remoteAddr, initiating))
        # the connection might have to be dropped (if we're already connected)
        resp = Process.receive()
        if not match(Command("connect"), resp):
            try:
                conn.close()
            except Exception:
                log.exception("socket.close() failed")
            return
        else:
            # we can use this connection
            self.onChildConnected(conn, remoteAddr, initiating, senderPid, messengerPid)
    
    def onChildConnected(self, conn, remoteAddr, initiating, senderPid, messengerPid):
        pass

    def onChildExited(self, m, childPid, state):
        if state.connectReceiver == childPid:
            state.connectReceiver = None
        if state.acceptReceiver == childPid:
            state.acceptReceiver = None
        if state.receiver == childPid:
            self._closeConnection(state)
            state.receiver = None
    
    def doDisconnect(self, m, state):
        self._closeConnection(state)

    def _closeConnection(self, state):
        if state.conn:
            remoteAddr = state.remoteAddr
            state.receiver = None
            # force threads blocked on recv (and send?) to return
            try:
                state.conn.shutdown(socket.SHUT_RDWR)
            except socket.error as e:
                if e.errno != os.errno.ENOTCONN:
                    raise
            except Exception:
                state.logger.exception("conn.shutdown() failed")
            # close the connection
            try:
                state.conn.close()
            except Exception:
                state.logger.exception("conn.close() failed")
            state.conn = None
            state.remoteAddr = None
            wasDisconnected = (state.connState == TcpSocket.CONNECTED)
            state.connState = TcpSocket.DISCONNECTED
        else:
            wasDisconnected = False
        if wasDisconnected:
            state.logger.info("Disconnected from %s." % repr(remoteAddr))
            self.disconnected()
    
    def _closeServer(self, state):
        if state.server:
            # force threads blocked on accept() to return
            try:
                state.server.shutdown(socket.SHUT_RDWR)
            except Exception:
                state.logger.exception("server.shutdown() failed")
            try:
                state.server.close()
            except Exception:
                state.logger.exception("server.close() failed")
            state.server = None