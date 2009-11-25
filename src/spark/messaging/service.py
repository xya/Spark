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

from __future__ import print_function
import sys
import os
import traceback
import types
import threading
import socket
import logging
from spark.async import Future, Delegate, threadedMethod, coroutine, PollReactor
from spark.messaging.common import AsyncMessenger
from spark.messaging.protocol import negociateProtocol

__all__ = ["Service", "MessengerService"]

class Service(object):
    """
    Base class for long-running tasks which can use a socket for communication.
    
    This class uses an asynchronous execution model. The reactor should be used
    for all perations (I/O and non-I/O), so that the service runs on a single thread.
    """
    
    # The service has not been started yet.
    UNSTARTED = 0
    # The service has been started, but is not connected to any peer.
    DISCONNECTED = 1
    # The service has been started, and has been requested to establish a connection.
    CONNECT_REQUESTED = 2
    # The service has been started, and is waiting for a connection to be established.
    CONNECTING = 3
    # The service has been started, and is connected to a peer.
    CONNECTED = 4
    # The service has been started and connected, and has been requested to close its connection.
    DICONNECT_REQUESTED = 5
    # The service has finished executing and released its resources.
    FINISHED = 6
    
    def __init__(self):
        super(Service, self).__init__()
        self.lock = threading.RLock()
        self.reactor = PollReactor(self.lock)
        self.state = Service.UNSTARTED
        self.conn = None
            
    def connect(self, address):
        """ Try to establish a connection with a remote peer with the specified address. """
        self._swapState(Service.DISCONNECTED, Service.CONNECT_REQUESTED)
        cont = Future()
        self.reactor.callback(self._connectRequest, cont, True, address)
        return cont
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        self._swapState(Service.DISCONNECTED, Service.CONNECT_REQUESTED)
        cont = Future()
        self.reactor.callback(self._connectRequest, cont, False, address)
        return cont
    
    def disconnect(self):
        self._swapState(Service.CONNECTED, Service.DISCONNECT_REQUESTED)
        cont = Future()
        self.reactor.callback(self._disconnectRequest, cont)
        return cont
    
    def _assertState(self, state, *otherStates):
        with self.lock:
            actualState = state
        if (actualState != state) and (not actualState in otherStates):
            raise Exception("The service is in the wrong state to do the operation")
        else:
            return actualState
    
    def _swapState(self, oldState, newState):
        with self.lock:
            if self.state == oldState:
                self.state = newState
            else:
                raise Exception("The service is in the wrong state to do the operation")

    def _connectRequest(self, cont, initiating, address):
        try:
            self._assertState(Service.CONNECT_REQUESTED)
            self._startSession(address, initiating, cont)
        except Exception:
            cont.failed()
    
    def _disconnectRequest(self, cont):
        try:
            self._assertState(Service.DISCONNECT_REQUESTED)
            self._endSession()
        except Exception:
            cont.failed()
        else:
            cont.completed()
    
    @coroutine
    def _startSession(self, address, initiating, cont):
        started = False
        try:
            # establish a connection and a protocol
            self.conn, remoteAddress = yield self._establishConnection(address, initiating)
            logging.info("Connected to %s", repr(remoteAddress))
            name = yield negociateProtocol(SocketFile(conn), initiating)
            logging.debug("Negociated protocol '%s'", name)
            
            # initialize the session, including derived classes' onConnected()
            self.onConnected(remoteAddress)
            started = True
            cont.completed(remoteAddress)
        except:
            if started:
                traceback.print_exc()
            else:
                cont.failed()
    
    @coroutine
    def _establishConnection(self, address, initiating):
        """ Establish a connection for the service, either with accept() or connect(). """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if initiating:
            yield self.reactor.connect(sock, address)
            yield sock, address
        else:
            try:
                sock.bind(address)
                sock.listen(1)
                conn, remoteAddr = yield self.reactor.accept(sock)
                yield conn, remoteAddr
            finally:
                sock.close()
    
    def _endSession(self):
        """ Close the connection and free all session-related resources. """
        if self.conn:
            # force threads blocked on recv (and send?) to return
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.conn.close()
            self.conn = None
            self.onDisconnected()
    
    def onConnected(self, remoteAddr):
        """ Called when a connection is established to the peer at 'remoteAddr'. """
        pass
    
    def onDisconnected(self):
        """ Called after a connection is terminated. """
        pass

class MessengerService(Service):
    """
    Base class for long-running tasks which can comunicate with messages.
    """
    def __init__(self):
        super(MessengerService, self).__init__()
        self.messenger = None
        self.recvOp = None
    
    def onConnected(self, remoteAddr):
        self.messenger = AsyncMessenger(SocketFile(self.conn))
        self.recvOp = self.messenger.receiveMessage()
        self.recvOp.after(self._messageReceived)
    
    def onDisconnected(self):
        self.recvOp.cancel()
        if hasattr(self.messenger, "close"):
            self.messenger.close()
        self.messenger = None
    
    def sendMessage(self, message):
        if self.messenger is None:
            raise Exception("The service has to be connected for sending messages.")
        return self.messenger.sendMessage(message)
    
    def _messageReceived(self, prev):
        try:
            message = prev.result
        except:
            message = None
            traceback.print_exc()
        
        if message is None:
            # we have been disconnected
            self._endSession()
        else:
            logging.debug("Received message: %s", message)
            self.onMessageReceived(message)
            self.recvOp = self.messenger.receiveMessage()
            self.recvOp.after(self._messageReceived)
    
    def onMessageReceived(self, message):
        """ This method is called when a message is received. """
        pass

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
    
    def read(self, size):
        try:
            return self.socket.recv(size)
        except socket.error as e:
            if e.errno == os.errno.ECONNRESET:
                return ""
            else:
                raise
    
    beginRead = threadedMethod(read)
    
    def beginWrite(self, data):
        cont = Future()
        try:
            self.write(data)
        except:
            return Future.failed()
        else:
            return Future.done()
    
    def write(self, data):
        #FIXME: check how many bytes have been sent
        self.socket.send(data)