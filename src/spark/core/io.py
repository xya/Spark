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

__all__ = ["TcpSocket", "TcpReceiver"]

class TcpSocket(ProcessBase):
    """ Base class for processes that can communicate using sockets. """
    def __init__(self):
        super(TcpSocket, self).__init__()
        self.listening = EventSender("listening", None)
        self.connected = EventSender("connected", None)
        self.disconnected = EventSender("disconnected")
    
    def connect(self, addr, family=socket.AF_INET, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("connect", addr, family, senderPid))
    
    def listen(self, addr, family=socket.AF_INET, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("listen", addr, family, senderPid))
    
    def accept(self, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("accept", senderPid))
    
    def disconnect(self):
        Process.send(self.pid, Command("disconnect"))

    def initState(self, state):
        super(TcpSocket, self).initState(state)
        state.isConnected = False
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
            Command("connect", None, int, int),
            Command("listen", None, int, int),
            Command("accept", int),
            Command("disconnect"),
            # internal messages
            Event("child-connected", None, None, bool),
            Event("child-exited", int))
    
    def cleanup(self, state):
        try:
            self._closeConnection(state)
            self._closeServer(state)
        finally:
            super(TcpSocket, self).cleanup(state)
    
    def createReceiver(self, state):
        return TcpReceiver()
    
    def doListen(self, m, bindAddr, family, senderPid, state):
        if (family != socket.AF_INET) and (family != socket.AF_INET6):
            Process.send(senderPid, Event("listen-error", "invalid-family"))
            return
        elif state.server:
            Process.send(senderPid, Event("listen-error", "invalid-state"))
            return
        server = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
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
        elif state.isConnected or not state.server:
            Process.send(senderPid, Event("accept-error", "invalid-state"))
            return
        state.acceptReceiver = self.createReceiver(state)
        state.acceptReceiver.start_linked()
        Process.send(state.acceptReceiver,
            Command("accept", state.server, senderPid, Process.current()))

    def doConnect(self, m, remoteAddr, family, senderPid, state):
        if (family != socket.AF_INET) and (family != socket.AF_INET6):
            Process.send(senderPid, Event("connection-error", "invalid-family"))
            return
        elif state.isConnected or state.connectReceiver:
            Process.send(senderPid, Event("connection-error", "invalid-state"))
            return
        state.connectReceiver = self.createReceiver(state)
        state.connectReceiver.start_linked()
        Process.send(state.connectReceiver,
            Command("connect", remoteAddr, family, senderPid, Process.current()))

    def onChildConnected(self, m, conn, remoteAddr, initiating, state):
        if initiating:
            receiver = state.connectReceiver
        else:
            receiver = state.acceptReceiver
        if state.receiver:
            state.logger.info("Dropping redundant connection to %s.", repr(remoteAddr))
            Process.send(receiver, Command("drop-connection"))
        else:
            # we're connected, update the process' state
            state.logger.info("Connected to %s.", repr(remoteAddr))
            state.isConnected = True
            state.conn = conn
            state.remoteAddr = remoteAddr
            state.receiver = receiver
            Process.send(receiver, Event("connected"))
            self.connected(remoteAddr)

    def onChildExited(self, m, childPid, state):
        connectPid = state.connectReceiver and state.connectReceiver.pid
        acceptPid = state.acceptReceiver and state.acceptReceiver.pid
        receivePid = state.receiver and state.receiver.pid
        if connectPid == childPid:
            state.connectReceiver = None
        if acceptPid == childPid:
            state.acceptReceiver = None
        if receivePid == childPid:
            self._closeConnection(state)
            state.receiver = None
    
    def doDisconnect(self, m, state):
        self._closeConnection(state)

    def _closeConnection(self, state):
        if state.conn:
            state.receiver = None
            TcpSocket.closeSocket(state.conn, state.logger)
            state.conn = None
            remoteAddr, state.remoteAddr = state.remoteAddr, None
            wasConnected, state.isConnected = state.isConnected, False
        else:
            wasConnected = False
        if wasConnected:
            state.logger.info("Disconnected from %s." % repr(remoteAddr))
            self.disconnected()
    
    def _closeServer(self, state):
        if state.server:
            TcpSocket.closeSocket(state.server, state.logger)
            state.server = None
    
    @classmethod
    def closeSocket(cls, sock, logger):
        # force threads blocked on recv/send/accept to return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error as e:
            if e.errno != os.errno.ENOTCONN:
                raise
        except Exception:
            logger.exception("Shutting down the socket failed.")
        # close the connection
        try:
            sock.close()
        except Exception:
            logger.exception("Closing the socket failed.")

class TcpReceiver(ProcessBase):
    def __init__(self, name=None):
        super(TcpReceiver, self).__init__(name)
    
    def initState(self, state):
        super(TcpReceiver, self).initState(state)
        state.initiating = None
        state.conn = None
        state.remoteAddr = None
        state.messengerPid = None
        state.senderPid = None
    
    def initPatterns(self, loop, state):
        super(TcpReceiver, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("accept", None, int, int),
            Command("connect", None, int, int, int),
            Command("drop-connection"),
            Event("connected"))
    
    def cleanup(self, state):
        try:
            if state.messengerPid:
                Process.try_send(state.messengerPid, Event("child-exited", self.pid))
        finally:
            super(TcpReceiver, self).cleanup(state)

    def doConnect(self, m, remoteAddr, family, senderPid, messengerPid, state):
        if state.conn:
            Process.send(messengerPid, Event("connection-error", "already-connected"))
            return
        state.initiating = True
        state.remoteAddr = remoteAddr
        state.senderPid = senderPid
        state.messengerPid = messengerPid
        conn = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if family == socket.AF_INET6:
            conn.bind(("::0", 0))
        else:
            conn.bind(("0.0.0.0", 0))
        state.logger.info("Connecting to %s.", repr(remoteAddr))
        try:
            conn.connect(remoteAddr)
        except socket.error as e:
            state.logger.error("Error while connecting: %s.", str(e))
            Process.send(senderPid, Event("connection-error", e))
            Process.exit()
        else:
            state.conn = conn
            self.confirmConnection(state)

    def doAccept(self, m, server, senderPid, messengerPid, state):
        if state.conn:
            Process.send(messengerPid, Event("accept-error", "already-connected"))
            return
        state.initiating = False
        state.senderPid = senderPid
        state.messengerPid = messengerPid
        state.logger.info("Waiting for a connection.")
        try:
            state.conn, state.remoteAddr = server.accept()
        except socket.error as e:
            # EINVAL error happens when shutdown() is called while waiting on accept()
            if e.errno != os.errno.EINVAL:
                state.logger.error("Error while accepting: %s.", str(e))
                Process.send(senderPid, Event("accept-error", e))
            Process.exit()
        else:
            self.confirmConnection(state)
    
    def confirmConnection(self, state):
        """ Notify the messenger process that a connection has been established. """
        Process.send(state.messengerPid,
            Event("child-connected", state.conn, state.remoteAddr, state.initiating))
    
    def doDropConnection(self, m, state):
        """ The connection has to be dropped (TcpSocket is connected using another socket). """
        TcpSocket.closeSocket(state.conn, state.logger)
        state.conn = None
        Process.exit()
    
    def onConnected(self, m, state):
        pass