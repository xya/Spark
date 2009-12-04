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

import sys
import os
import traceback
import types
import threading
import socket
import logging
from functools import wraps
from spark.async import Future, Delegate, coroutine, TaskFailedError
from spark.messaging.common import AsyncMessenger, MessageDelivery
from spark.messaging.protocol import negociateProtocol
from spark.messaging.messages import Request, Response, Notification

__all__ = ["Service", "Transport", "TcpTransport", "MessagingSession"]

class Transport(object):
    """
    Base class for transports, which are used by sessions for communicating.
    """
    
    # The transport is not connected to any peer.
    DISCONNECTED = 0
    # The transport has been requested to establish a connection.
    CONNECTING = 1
    # The transport is connected to a peer.
    CONNECTED = 2
    
    def __init__(self):
        super(Transport, self).__init__()
        self.connected = Delegate()
        self.disconnected = Delegate()
    
    def connect(self, address):
        """ Try to establish a connection with a remote peer at the specified address. """
        raise NotImplementedError()
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        raise NotImplementedError()
    
    def disconnect(self):
        """ Close an established connection. """
        raise NotImplementedError()
    
    @property
    def connection(self):
        """ If a connection has been established, file-like object which can be used to communicate."""
        raise NotImplementedError()
    
    def onConnected(self, initiating):
        """ Fires the 'connected' event when a connection is established."""
        self.connected(initiating)
    
    def onDisconnected(self):
        """ Fires the 'disconnected' event when a connection is closed. """
        self.disconnected()

class TcpTransport(Transport):
    """
    Transport which use a TCP/IP socket for communications.
    
    This class uses an asynchronous execution model. The reactor should be used
    for all operations (I/O and non-I/O), so that the session runs on a single thread.
    """
    
    def __init__(self, reactor, name=None):
        super(TcpTransport, self).__init__()
        self.logger = logging.getLogger(name)
        self.reactor = reactor
        self.conn = None
        self.remoteAddr = None
        self.connState = Transport.DISCONNECTED
    
    def connect(self, address):
        """ Try to establish a connection with a remote peer at the specified address. """
        cont = Future()
        self.reactor.post(self._connectRequest, cont, True, address)
        return cont
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        cont = Future()
        self.reactor.post(self._connectRequest, cont, False, address)
        return cont
    
    def disconnect(self):
        """ Close an established connection. """
        return self.reactor.send(self._closeConnection)
    
    @property
    def connection(self):
        """ If a connection has been established, file-like object which can be used to communicate."""
        return self.conn
    
    def _connectRequest(self, cont, initiating, address):
        if self.connState == Transport.CONNECTED:
            cont.failed(Exception("The service is already connected"))
        elif self.connState == Transport.CONNECTING:
            cont.failed(Exception("The service is already trying to connect"))
        cont.run_coroutine(self._startConnection(address, initiating))
    
    def _startConnection(self, address, initiating):
        try:
            sock = self.reactor.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            if initiating:
                self.connState = Transport.CONNECTING
                yield sock.beginConnect(address)
                self.conn, self.remoteAddr = sock, address
            else:
                try:
                    sock.bind(address)
                    sock.listen(1)
                    self.connState = Transport.CONNECTING
                    self.conn, self.remoteAddr = yield sock.beginAccept()
                finally:
                    sock.close()
            self.connState = Transport.CONNECTED
            self.logger.info("Connected to %s", repr(self.remoteAddr))
            self.reactor.post(self.onConnected, initiating)
        except:
            self._closeConnection()
            raise
        yield self.remoteAddr
    
    def _closeConnection(self):
        """ If there is an active connection, close it. """
        if self.conn:
            self.logger.info("Disconnecting from %s" % repr(self.remoteAddr))
            # force threads blocked on recv (and send?) to return
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except socket.error as e:
                if e.errno != os.errno.ENOTCONN:
                    raise
            except Exception:
                self.logger.exception("socket.shutdown() failed")
            # close the connection
            try:
                self.conn.close()
            except Exception:
                self.logger.exception("socket.close() failed")
            self.conn = None
            self.remoteAddr = None
            wasDisconnected = (self.connState == Transport.CONNECTED)
            self.connState = Transport.DISCONNECTED
        else:
            wasDisconnected = False
        
        if wasDisconnected:
            self.onDisconnected()

def toCamelCase(tag):
    """ Convert the tag to camel case (e.g. "create-transfer" becomes "createTransfer"). """
    words = tag.split("-")
    first = words.pop(0)
    words = [word.capitalize() for word in words]
    words.insert(0, first)
    return "".join(words)

def toPascalCase(tag):
    """ Convert the tag to Pascal case (e.g. "create-transfer" becomes "CreateTransfer"). """
    return "".join([word.capitalize() for word in tag.split("-")])

class MessagingSession(MessageDelivery):
    """
    Session where messages are used to communicate on top of a transport.
    """
    def __init__(self, transport, name=None):
        super(MessagingSession, self).__init__()
        self.logger = logging.getLogger(name)
        self.transport = transport
        self.messenger = None
        self.service = None
        self.startWaiters = []
        self.endWaiters = []
        self.__lock = threading.RLock()
        transport.connected += self._connected
        transport.disconnected += self._disconnected
    
    def _connected(self, initiating):
        self.logger.debug("Negociating protocol")
        conn = self.transport.connection
        if conn is None:
            self.logger.error("Connection object is None")
        else:
            negociateProtocol(conn, initiating).after(self._protocolNegociated)
    
    def _protocolNegociated(self, prev):
        try:
            name = prev.result
        except TaskFailedError as e:
            type, val, tb = e.inner()
            if not isinstance(val, EOFError):
                self.logger.exception("Error while negociating protocol")
            self.transport.disconnect()
        else:
            self.logger.debug("Negociated protocol '%s'", name)
            self.messenger = AsyncMessenger(self.transport.connection)
            if self.service is not None:
                self.service.start()
            with self.__lock:
                waiters, self.startWaiters = self.startWaiters, []
            self._signalWaiters(waiters)
            self.messenger.receiveMessage().after(self._messageReceived)
    
    def _disconnected(self):
        if hasattr(self.messenger, "close"):
            self.messenger.close()
        self.messenger = None
        self.resetDelivery()
        if self.service is not None:
            self.service.stop()
        with self.__lock:
            waiters, self.endWaiters = self.endWaiters, []
        self._signalWaiters(waiters)
    
    def registerService(self, service):
        """ Define to which service the requests should be delivered to. """
        self.service = service
    
    def sendMessage(self, message):
        """ Send a message to the connected peer if there is an active session. """
        if not self.isActive:
            raise Exception("The session must be active for sending messages.")
        self.logger.debug("Sending message: %s", message)
        return self.messenger.sendMessage(message)
    
    def _messageReceived(self, prev):
        try:
            message = prev.result
        except TaskFailedError as e:
            type, val, tb = e.inner()
            if not isinstance(val, EOFError):
                self.logger.exception("Error while receiving a message")
            message = None
        
        if message is None:
            # we have been disconnected
            self.transport.disconnect()
        else:
            self.logger.debug("Received message: %s", message)
            if self.service is not None:
                self.deliverMessage(message, self.service)
            if self.messenger is not None:
                self.messenger.receiveMessage().after(self._messageReceived)
    
    @property
    def isActive(self):
        """
        Indicate whether the session is currently active,
        i.e. messages can be sent and received.
        """
        return self.messenger is not None
    
    def waitActive(self):
        """ Return a future which can be used to wait until the session is active. """
        if self.isActive:
            return Future.done()
        cont = Future()
        with self.__lock:
            self.startWaiters.append(cont)
        return cont
    
    def waitInactive(self):
        """ Return a future which can be used to wait until the session is inactive. """
        if not self.isActive:
            return Future.done()
        cont = Future()
        with self.__lock:
            self.endWaiters.append(cont)
        return cont
    
    def _signalWaiters(self, waiters):
        for waiter in waiters:
            try:
                waiter.completed()
            except Exception:
                self.logger.exception("Error when signaling 'endSession' waiter")

class Service(object):
    """ A service exposes a set of operations through requests and notifications. """
    def __init__(self, session, name=None):
        super(Service, self).__init__()
        self.session = session
        self.logger = logging.getLogger(name)
    
    def start(self):
        """ Start the service. The session must be currently active. """
        pass
    
    def stop(self):
        """ Stop the service, probably because the session ended. """
        pass
    
    def onMessageReceived(self, message):
        """
        This method is called when a message (other than a request,
        response or notification) is received.
        """
        pass
    
    def onRequestReceived(self, req):
        """ Invoke the relevant request handler and send back the results.  """
        methodName = "request" + toPascalCase(req.tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            try:
                self.logger.debug("Executing request handler '%s'" % req.tag)
                results = method(req)
                assert not isinstance(results, Future), "Request handler returned a future"
            except Exception as e:
                self.logger.exception("Error while executing request handler")
                self._sendErrorReponse(req, e)
            else:
                self.session.sendResponse(req, results)
        else:
            self._sendErrorReponse(req, NotImplementedError())
    
    def sendRequest(self, tag, params=None):
        """
        Send a request to the connected peer. When the peer answers,
        invoke the relevant response handler.
        """
        req = Request(tag, params)
        self.session.sendRequest(req).after(self._responseReceived, tag)
    
    def _responseReceived(self, prev, tag):
        """ Invoke the relevant response handler.  """
        methodName = "response" + toPascalCase(tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            method(prev)
    
    def _sendErrorReponse(self, req, e):
        """ Send a response indicating the request failed because of the exception. """
        self.session.sendResponse(req, {"error":
            {"type": e.__class__.__name__, "message": str(e)}
        })
    
    def sendNotification(self, tag, params=None):
        """ Send a notification to the connected peer. """
        self.session.sendNotification(Notification(tag, params))
    
    def onNotificationReceived(self, n):
        """ Invoke the relevant notification handler. """
        methodName = "notification" + toPascalCase(n.tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            method(n)