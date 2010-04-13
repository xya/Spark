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

import os
import socket
import logging
from collections import Sequence
from spark.async import *
from spark.messaging.protocol import *
from spark.messaging.messages import *

__all__ = ["TcpMessenger", "Service"]

class TcpMessenger(ProcessBase):
    # The messenger is not connected to any peer.
    DISCONNECTED = 0
    # The messenger is connected to a peer.
    CONNECTED = 1
    
    def __init__(self):
        self.listening = EventSender("listening", None)
        self.connected = EventSender("connected", None)
        self.protocolNegociated = EventSender("protocol-negociated", basestring)
        self.disconnected = EventSender("disconnected")
        self.pid = Process.spawn(self.run, name="TcpMessenger")
    
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

    def send(self, message, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("send", message, senderPid))
    
    def close(self):
        Process.try_send(self.pid, Command("stop"))
    
    def initState(self, state):
        state.connState = TcpMessenger.DISCONNECTED
        state.server = None
        state.conn = None
        state.remoteAddr = None
        state.recipient = None
        state.protocol = None
        state.stream = None
        state.writer = None
        state.receiver = None
        state.acceptReceiver = None
        state.connectReceiver = None
        state.logger = Process.logger()
    
    def initPatterns(self, loop, state):
        loop.addPattern(Command("stop"), result=False)
        loop.addHandlers(self,
            # public messages
            Command("connect", None, int),
            Command("listen", None, int),
            Command("accept", int),
            Command("disconnect"),
            Command("send", None, int),
            # internal messages
            Event("connected", None, None, bool),
            Event("end-of-stream", int))
    
    def cleanup(self, state):
        self._closeConnection(state)
        self._closeServer(state)
    
    def doListen(self, m, bindAddr, senderPid, state):
        if state.server:
            Process.send(senderPid, Event("listen-error", "invalid-state"))
            return
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            state.logger.info("Listening to incoming connections on %s.", repr(m[2]))
            server.bind(bindAddr)
            server.listen(1)
            self.listening(bindAddr)
        except socket.error as e:
            Process.send(senderPid, Event("listen-error", e))
        else:
            state.server = server
    
    def doAccept(self, m, senderPid, state):
        if state.acceptReceiver:
            # we are already waiting for an incoming connection
            return
        elif (state.connState != TcpMessenger.DISCONNECTED) or not state.server:
            Process.send(senderPid, Event("accept-error", "invalid-state"))
            return
        args = (state.server, senderPid, Process.current())
        state.acceptReceiver = Process.spawn(self._waitForAccept, args, "TcpServer")

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
                log.error(str(e))
                Process.send(senderPid, Event("accept-error", e))
        else:
            self._startSession(conn, remoteAddr, False, senderPid, messengerPid)

    def doConnect(self, m, remoteAddr, senderPid, state):
        if (state.connState != TcpMessenger.DISCONNECTED) or state.connectReceiver:
            Process.send(senderPid, Event("connection-error", "invalid-state"))
            return
        args = (remoteAddr, senderPid, Process.current())
        state.connectReceiver = Process.spawn(self._waitForConnect, args, "TcpClient")
    
    def _waitForConnect(self, remoteAddr, senderPid, messengerPid):
        log = Process.logger()
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        conn.bind(("0.0.0.0", 0))
        log.info("Connecting to %s.", repr(remoteAddr))
        try:
            conn.connect(remoteAddr)
        except socket.error as e:
            log.error(str(e))
            Process.send(senderPid, Event("connection-error", e))
        else:
            self._startSession(conn, remoteAddr, True, senderPid, messengerPid)

    def onConnected(self, m, conn, remoteAddr, initiating, state):
        if initiating:
            receiver = state.connectReceiver
            state.connectReceiver = None
        else:
            receiver = state.acceptReceiver
            state.acceptReceiver = None
        if state.receiver:
            state.logger.info("Dropping redundant connection to %s.", repr(remoteAddr))
            Process.send(receiver, Command("close"))
        else:
            # we're connected, update the process' state
            state.logger.info("Connected to %s.", repr(remoteAddr))
            state.connState = TcpMessenger.CONNECTED
            state.conn = conn
            state.remoteAddr = remoteAddr
            state.receiver = receiver
            stream = SocketWrapper(state.conn)
            self.connected(remoteAddr)
            # negociate the protocol to use for formatting messages
            name = negociateProtocol(stream, initiating)
            state.logger.info("Negociated protocol '%s'.", name)
            state.stream = stream
            state.protocol = name
            state.writer = messageWriter(stream, name)
            self.protocolNegociated(name)
            # start receiving messages
            Process.send(receiver, Command("receive", stream, name))
    
    def _startSession(self, conn, remoteAddr, initiating, senderPid, messengerPid):
        log = Process.logger()
        # notify the messenger process that we have established a connection
        Process.send(messengerPid, Event("connected", conn, remoteAddr, initiating))
        # the connection might have to be dropped (if we're already connected)
        resp = Process.receive()
        if not match(Command("receive", None, basestring), resp):
            try:
                conn.close()
            except Exception:
                log.exception("socket.close() failed")
            return
        # we can use this connection. start receiving messages
        reader = messageReader(resp[2], resp[3])
        try:
            while True:
                m = reader.read()
                if m is None:
                    break
                else:
                    log.info("Received message %s." % repr(m))
                    Process.send(senderPid, m)
        finally:
            Process.try_send(messengerPid, Event("end-of-stream", senderPid))
    
    def onEndOfStream(self, m, snderPid, state):
        self._closeConnection(state)
        self.disconnected()
    
    def doSend(self, m, data, senderPid, state):
        if (state.connState != TcpMessenger.CONNECTED) or state.protocol is None:
            Process.send(senderPid, Event("send-error", "invalid-state"))
            return
        state.logger.info("Sending message %s." % repr(data))
        state.writer.write(data)
    
    def doDisconnect(self, m, state):
        self._closeConnection(state)

    def _closeConnection(self, state):
        if state.conn:
            state.logger.info("Disconnecting from %s." % repr(state.remoteAddr))
            state.stream = None
            state.protocol = None
            state.writer = None
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
            state.connState = TcpMessenger.DISCONNECTED
    
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

class SocketWrapper(object):
    def __init__(self, sock):
        self.sock = sock
        self.write = sock.send
    
    def read(self, size):
        try:
            return self.sock.recv(size)
        except socket.error as e:
            if (e.errno == os.errno.ECONNRESET) or (e.errno == os.errno.EBADF):
                return ""
            else:
                raise

class Service(ProcessBase):
    """ Base class for services that handle requests using messaging. """
    def __init__(self):
        self.connected = EventSender("connected")
        self.connectionError = EventSender("connection-error", None)
        self.disconnected = EventSender("disconnected")
    
    def initState(self, state):
        state.bindAddr = None
        state.messenger = TcpMessenger()
        state.nextTransID = 1
    
    def initPatterns(self, loop, state):
        m = state.messenger
        loop.addPattern(Command("stop"), result=False)
        loop.addHandlers(self,
            # messages received from TcpMessenger
            m.protocolNegociated.suscribe(),
            m.disconnected.suscribe(),
            Event("connection-error", None),
            # messages received from the caller
            Command("connect", None),
            Command("bind", None),
            Command("disconnect"))
    
    def cleanup(self, state):
        state.messenger.close()
    
    def onConnectionError(self, m, error, state):
        self.connectionError(error)
    
    def onProtocolNegociated(self, m, protocol, state):
        self.connected()
    
    def onDisconnected(self, m, state):
        self.disconnected()
        if state.bindAddr:
            state.messenger.accept()
    
    def doConnect(self, m, remoteAddr, state):
        state.messenger.connect(remoteAddr)
    
    def doBind(self, m, bindAddr, state):
        if not state.bindAddr:
            state.bindAddr = bindAddr
            state.messenger.listen(state.bindAddr)
            state.messenger.accept()
    
    def doDisconnect(self, m, state):
        state.messenger.disconnect()
    
    def _newTransID(self, state):
        transID = state.nextTransID
        state.nextTransID += 1
        return transID
    
    def sendRequest(self, state, tag, *params):
        """ Send a request. """
        transID = self._newTransID(state)
        state.messenger.send(Request(tag, *params).withID(transID))
    
    def sendResponse(self, state, req, *params):
        """ Send a response to a request. """
        state.messenger.send(Response(req.tag, *params).withID(req.transID))
    
    def sendNotification(self, state, tag, *params):
        """ Send a notification. """
        transID = self._newTransID(state)
        state.messenger.send(Notification(tag, *params).withID(transID))