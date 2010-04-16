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
from spark.messaging.protocol import *
from spark.messaging.messages import *

__all__ = ["TcpMessenger", "Service"]

class TcpMessenger(TcpSocket):
    """ Process that can send and receive messages using a socket. """
    def __init__(self):
        super(TcpMessenger, self).__init__()
        self.protocolNegociated = EventSender("protocol-negociated", basestring)
    
    def send(self, message, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("send", message, senderPid))

    def initState(self, state):
        super(TcpMessenger, self).initState(state)
        state.protocol = None
        state.writer = None
    
    def initPatterns(self, loop, state):
        super(TcpMessenger, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("send", None, int),
            Event("protocol-negociated", basestring))
    
    def createReceiver(self, state):
        return TcpMessageReceiver()
    
    def onProtocolNegociated(self, m, protocol, state):
        stream = SocketWrapper(state.conn)
        state.protocol = protocol
        state.writer = messageWriter(stream, protocol)
        self.protocolNegociated(protocol)
    
    def doSend(self, m, data, senderPid, state):
        if not state.isConnected or state.writer is None:
            Process.send(senderPid, Event("send-error", "invalid-state", data))
            return
        try:
            state.writer.write(data)
        except socket.error as e:
            state.logger.error("Error while sending: %s.", str(e))
            if e.errno == os.errno.EPIPE:
                # the remote peer reset the connection
                raise ProcessExit("connection-reset")
            else:
                raise

    def _closeConnection(self, state):
        try:
            state.protocol = None
            state.writer = None
        finally:
            super(TcpMessenger, self)._closeConnection(state)

class TcpMessageReceiver(TcpReceiver):
    def __init__(self, name="TcpReceiver"):
        super(TcpMessageReceiver, self).__init__(name)
        
    def initState(self, state):
        super(TcpMessageReceiver, self).initState(state)
        state.reader = None
        
    def onConnected(self, m, state):
        # negociate the protocol to use for formatting messages
        stream = SocketWrapper(state.conn)
        name = negociateProtocol(stream, state.initiating)
        state.logger.info("Negociated protocol '%s'.", name)
        Process.send(state.messengerPid, Event("protocol-negociated", name))
        # start receiving messages
        state.reader = messageReader(stream, name)
        try:
            self.receiveMessages(state)
        except socket.error as e:
            state.logger.error("Error while receiving: %s.", str(e))
            if e.errno == os.errno.ECONNRESET:
                raise ProcessExit("connection-reset")
            else:
                raise
    
    def receiveMessages(self, state):
        while True:
            m = state.reader.read()
            if m is None:
                raise ProcessExit()
            else:
                Process.send(state.senderPid, m)

class SocketWrapper(object):
    def __init__(self, sock):
        self.sock = sock
        self.read = sock.recv
        self.write = sock.send

class Service(ProcessBase):
    """ Base class for services that handle requests using messaging. """
    def __init__(self):
        super(Service, self).__init__()
        self.connected = EventSender("connected", None)
        self.connectionError = EventSender("connection-error", None)
        self.listening = EventSender("listening", None)
        self.listenError = EventSender("listen-error", None)
        self.disconnected = EventSender("disconnected")
    
    def initState(self, state):
        super(Service, self).initState(state)
        state.bindAddr = None
        state.connAddr = None
        state.isConnected = False
        state.messenger = TcpMessenger()
        state.nextTransID = 1
    
    def initPatterns(self, loop, state):
        super(Service, self).initPatterns(loop, state)
        m = state.messenger
        loop.addHandlers(self,
            # messages received from TcpMessenger
            m.listening.suscribe(),
            Event("listen-error", None),
            m.connected.suscribe(),
            m.protocolNegociated.suscribe(),
            m.disconnected.suscribe(),
            Event("connection-error", None),
            # messages received from the caller
            Command("connect", None),
            Command("bind", None),
            Command("disconnect"))
    
    def onStart(self, state):
        super(Service, self).onStart(state)
        state.messenger.start_linked()
    
    def cleanup(self, state):
        try:
            state.messenger.stop()
        finally:
            super(Service, self).cleanup(state)
    
    def onListening(self, m, bindAddr, state):
        self.listening(bindAddr)
        state.messenger.accept()
    
    def onListenError(self, m, error, state):
        self.listenError(error)
    
    def onConnected(self, m, connAddr, state):
        state.connAddr = connAddr
    
    def onConnectionError(self, m, error, state):
        self.connectionError(error)
    
    def onProtocolNegociated(self, m, protocol, state):
        state.isConnected = True
        self.connected(state.connAddr)
        self.sessionStarted(state)
    
    def onDisconnected(self, m, state):
        state.connAddr = None
        state.isConnected = False
        self.disconnected()
        self.sessionEnded(state)
        if state.bindAddr:
            state.messenger.accept()
    
    def doConnect(self, m, remoteAddr, state):
        state.messenger.connect(remoteAddr, socket.AF_INET)
    
    def doBind(self, m, bindAddr, state):
        if not state.bindAddr:
            state.bindAddr = bindAddr
            state.messenger.listen(state.bindAddr, socket.AF_INET)
    
    def doDisconnect(self, m, state):
        state.messenger.disconnect()
    
    def _newTransID(self, state):
        transID = state.nextTransID
        state.nextTransID += 1
        return transID
    
    def sessionStarted(self, state):
        """ This method is called when the messaging session has just started. """
        pass
    
    def sessionEnded(self, state):
        """ This method is called when the messaging session has just ended. """
        pass
    
    def sendRequest(self, state, tag, *params):
        """ Send a request. """
        if not hasattr(state, "nextTransID"):
            raise TypeError("First argument should be the process' state")
        transID = self._newTransID(state)
        state.messenger.send(Request(tag, *params).withID(transID))
    
    def sendResponse(self, state, req, *params):
        """ Send a response to a request. """
        if not hasattr(state, "nextTransID"):
            raise TypeError("First argument should be the process' state")
        state.messenger.send(Response(req.tag, *params).withID(req.transID))
    
    def sendNotification(self, state, tag, *params):
        """ Send a notification. """
        if not hasattr(state, "nextTransID"):
            raise TypeError("First argument should be the process' state")
        transID = self._newTransID(state)
        state.messenger.send(Notification(tag, *params).withID(transID))