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
from spark.async import Future, Delegate, coroutine
from spark.messaging.common import AsyncMessenger, MessageDelivery
from spark.messaging.protocol import negociateProtocol
from spark.messaging.messages import Request, Response, Notification

__all__ = ["Service", "MessengerService", "serviceMethod"]

def serviceMethod(func):
    """ Decorator which invokes the function on the service's thread. """
    @wraps(func)
    def invoker(self, *args, **kwargs):
        #return self.reactor.send(func, self, *args, **kwargs)
        cont = Future()
        self.reactor.post(cont.run, func, self, *args, **kwargs)
        return cont
    return invoker

class Service(object):
    """
    Base class for long-running tasks which can use a socket for communication.
    
    This class uses an asynchronous execution model. The reactor should be used
    for all perations (I/O and non-I/O), so that the service runs on a single thread.
    """
    
    # The service is not connected to any peer.
    DISCONNECTED = 0
    # The service has been requested to establish a connection.
    CONNECTING = 1
    # The service is connected to a peer.
    CONNECTED = 2
    
    def __init__(self, reactor, name=None):
        super(Service, self).__init__()
        self.logger = logging.getLogger(name)
        self.reactor = reactor
        self.conn = None
        self.remoteAddr = None
        self.connState = Service.DISCONNECTED
        self.onConnected = Delegate()
        self.onDisconnected = Delegate()
    
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
        cont = Future()
        self.reactor.post(self._disconnectRequest, cont)
        return cont
    
    def _connectRequest(self, cont, initiating, address):
        if self.connState == Service.CONNECTED:
            cont.failed(Exception("The service is already connected"))
        elif self.connState == Service.CONNECTING:
            cont.failed(Exception("The service is already trying to connect"))
        cont.run_coroutine(self._startConnection(address, initiating))
    
    def _disconnectRequest(self, cont):
        try:
            self._closeConnection()
        except Exception:
            cont.failed()
        else:
            cont.completed()
    
    def _startConnection(self, address, initiating):
        try:
            sock = self.reactor.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            if initiating:
                self.connState = Service.CONNECTING
                yield sock.beginConnect(address)
                self.conn, self.remoteAddr = sock, address
            else:
                try:
                    sock.bind(address)
                    sock.listen(1)
                    self.connState = Service.CONNECTING
                    self.conn, self.remoteAddr = yield sock.beginAccept()
                finally:
                    sock.close()
            self.connState = Service.CONNECTED
            self.logger.info("Connected to %s", repr(self.remoteAddr))
            self.reactor.post(self.onConnected, self.remoteAddr, initiating)
        except:
            self._closeConnection()
            raise
        yield self.remoteAddr
    
    def _closeConnection(self):
        """ If there is an active connection, close it. """
        if self.conn:
            # force threads blocked on recv (and send?) to return
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except socket.error as e:
                if e.errno != os.errno.ENOTCONN:
                    raise
            except Exception:
                self.logger.exception("socket.shutdown() failed")
            # close the connection
            self.logger.info("Disconnected from %s" % repr(self.remoteAddr))
            try:
                self.conn.close()
            except Exception:
                self.logger.exception("socket.close() failed")
            self.conn = None
            self.remoteAddr = None
            wasDisconnected = (self.connState == Service.CONNECTED)
            self.connState = Service.DISCONNECTED
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

class MessengerService(Service):
    """
    Base class for long-running tasks which can comunicate using messages.
    """
    def __init__(self, reactor, name=None):
        super(MessengerService, self).__init__(reactor, name)
        self.onConnected += self._connected
        self.onDisconnected += self._disconnected
        self.delivery = MessageDelivery()
        self.delivery.sendMessage = self.sendMessage
        self.delivery.messageReceived += self.messageReceived
        self.delivery.requestReceived += self._requestReceived
        self.delivery.notificationReceived += self._notificationReceived
        self.messenger = None
    
    def _connected(self, remoteAddr, initiating):
        self.logger.debug("Negociating protocol")
        negociateProtocol(self.conn, initiating).after(self._protocolNegociated)
    
    def _protocolNegociated(self, prev):
        try:
            name = prev.result
        except:
            self.logger.exception("Error while negociating protocol")
            self._closeConnection()
        else:
            self.logger.debug("Negociated protocol '%s'", name)
            self.messenger = AsyncMessenger(self.conn)
            self.sessionStarted()
            self.messenger.receiveMessage().after(self._messageReceived)
    
    def _disconnected(self):
        if hasattr(self.messenger, "close"):
            self.messenger.close()
        self.messenger = None
        self.delivery.resetDelivery()
        self.sessionEnded()
    
    def sendMessage(self, message):
        """ Send a message to the connected peer if there is an active session. """
        if not self.isSessionActive:
            raise Exception("A session has be active for sending messages.")
        self.logger.debug("Sending message: %s", message)
        return self.messenger.sendMessage(message)
    
    def _messageReceived(self, prev):
        if self.messenger is None:
            # spurious message after we disconnected
            return
        
        try:
            message = prev.result
        except:
            message = None
            self.logger.exception("Error while receiving a message")
        
        if message is None:
            # we have been disconnected
            self._closeConnection()
        else:
            self.logger.debug("Received message: %s", message)
            self.delivery.deliverMessage(message)
            self.messenger.receiveMessage().after(self._messageReceived)
    
    def _requestReceived(self, req):
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
                self.delivery.sendResponse(req, results)
        else:
            self._sendErrorReponse(req, NotImplementedError())
    
    def sendRequest(self, tag, params=None):
        """
        Send a request to the connected peer. When the peer answers,
        invoke the relevant response handler.
        """
        req = Request(tag, params)
        self.delivery.sendRequest(req).after(self._responseReceived, tag)
    
    def _responseReceived(self, prev, tag):
        """ Invoke the relevant response handler.  """
        methodName = "response" + toPascalCase(tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            method(prev)
    
    def _sendErrorReponse(self, req, e):
        """ Send a response indicating the request failed because of the exception. """
        self.delivery.sendResponse(req, {"error":
            {"type": e.__class__.__name__, "message": str(e)}
        })
    
    def sendNotification(self, tag, params=None):
        """ Send a notification to the connected peer. """
        self.delivery.sendNotification(Notification(tag, params))
    
    def _notificationReceived(self, n):
        """ Invoke the relevant notification handler. """
        methodName = "notification" + toPascalCase(n.tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            method(n)
    
    @property
    def isSessionActive(self):
        """
        Indicate whether a session is currently active,
        i.e. messages can be sent and received
        """
        return self.messenger is not None
    
    def sessionStarted(self):
        """
        This method is called when a session has started,
        i.e. messages can be sent and received.
        """
        pass
    
    def sessionEnded(self):
        """
        This method is called when a session has ended,
        i.e. messages can't be sent or received anymore.
        """
        pass
    
    def messageReceived(self, message):
        """
        This method is called when a message (other than a request,
        response or notification) is received.
        """
        pass