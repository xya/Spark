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
            Command("add-recipient", None, int),
            Event("protocol-negociated", basestring))
    
    def createReceiver(self, state):
        return TcpMessageReceiver()
    
    def onProtocolNegociated(self, m, protocol, state):
        stream = SocketWrapper(state.conn)
        state.protocol = protocol
        state.writer = messageWriter(stream, protocol)
        self.protocolNegociated(protocol)
    
    def addRecipient(self, pattern, pid):
        """ Add a recipient to the message delivery table.
        All messages matching the pattern will be sent to the process 'pid'. """
        Process.send(self.pid, Command("add-recipient", pattern, pid))
    
    def doAddRecipient(self, m, pattern, pid, state):
        if state.receiver:
            Process.send(state.receiver.pid, m)
    
    def doSend(self, m, data, senderPid, state):
        if not state.isConnected or state.writer is None:
            Process.send(senderPid, Event("send-error", "invalid-state", data))
            return
        try:
            state.writer.write(data)
        except socket.error as e:
            state.logger.error("Error while sending: %s.", str(e))
            #TODO: constants for Winsock errors
            if (e.errno == os.errno.EPIPE) or (e.errno == 10053):
                # the remote peer reset the connection
               Process.exit("connection-reset")
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
        state.routes = None
    
    def initPatterns(self, loop, state):
        super(TcpMessageReceiver, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("add-recipient", None, int))    
    
    def onConnected(self, m, state):
        # negociate the protocol to use for formatting messages
        stream = SocketWrapper(state.conn)
        try:
            name = negociateProtocol(stream, state.initiating)
        except socket.error as e:
            if (e.errno == os.errno.ECONNRESET) or (e.errno == 10054):
                Process.exit("connection-reset")
            else:
                raise
        state.logger.info("Negociated protocol '%s'.", name)
        Process.send(state.messengerPid, Event("protocol-negociated", name))
        state.reader = messageReader(stream, name)
        # start receiving messages
        self.receiveMessages(state)
    
    def receiveMessages(self, state):
        state.routes = []
        try:
            while True:
                rm = state.reader.read()
                if rm is None:
                    Process.exit()
                self.deliverRemoteMessage(rm, state)
                # check if the process has received any message while receiving from the socket
                ok, lm = Process.try_receive()
                if ok:
                    self.handleMessage(lm, state)
        except socket.error as e:
            if e.errno == 10058:
                # shutdown() was called while waiting on recv()
                Process.exit()
            else:
                state.logger.error("Error while receiving: %s.", str(e))
                if e.errno == os.errno.ECONNRESET:
                     Process.exit("connection-reset")
                else:
                     raise
    
    def deliverRemoteMessage(self, m, state):
        """ Deliver the message we received from the socket to the right recipient. """
        recipient = state.senderPid
        if state.routes:
            for pattern, pid in state.routes:
                 if match(pattern, m):
                    recipient = pid
                    break
        Process.send(recipient, m)
    
    def doAddRecipient(self, m, pattern, pid, state):
        """ Add a recipient to the message delivery table.
        All messages matching the pattern will be sent to the process 'pid'. """
        state.routes.insert(0, (pattern, pid))

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