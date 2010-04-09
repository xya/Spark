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
from collections import Mapping
from functools import wraps
from spark.async import Future, Delegate, coroutine, TaskFailedError, process
from spark.messaging.common import AsyncMessenger, MessageDelivery
from spark.messaging.protocol import negociateProtocol, messageReader, messageWriter
from spark.messaging.messages import Request, Response, Notification, match

__all__ = ["Service", "Transport", "TcpTransport", "PipeTransport", "MessagingSession"]

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
                sock.bind(("0.0.0.0", 0))
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
            self.onConnected(initiating)
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

class PipeTransport(Transport):
    """
    Transport which use a pipe for communications, intended for testing.
    
    This class uses an asynchronous execution model. The reactor should be used
    for all operations (I/O and non-I/O), so that the session runs on a single thread.
    """
    def __init__(self, reactor, pipe, name=None):
        super(PipeTransport, self).__init__()
        self.logger = logging.getLogger(name)
        self.reactor = reactor
        self.pipe = pipe
        self.connState = Transport.DISCONNECTED
    
    def connect(self, address):
        """ Try to establish a connection with a remote peer at the specified address. """
        return self.reactor.send(self._connectRequest, True)
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        return self.reactor.send(self._connectRequest, False)
    
    def disconnect(self):
        """ Close an established connection. """
        return self.reactor.send(self._closeConnection)
    
    @property
    def connection(self):
        """ If a connection has been established, file-like object which can be used to communicate."""
        if self.connState == Transport.CONNECTED:
            return self.pipe
        else:
            return None
    
    def _connectRequest(self, initiating):
        if (self.connState == Transport.DISCONNECTED) and self.pipe is not None:
            self.connState = Transport.CONNECTED
            self.onConnected(initiating)
        else:
            raise Exception("Invalid state")
    
    def _closeConnection(self):
        """ If there is an active connection, close it. """
        if self.connState == Transport.CONNECTED:
            self.logger.info("Disconnecting pipe")
            try:
                self.pipe.close()
            except Exception:
                self.logger.exception("pipe.close() failed")
            self.pipe = None
            self.connState = Transport.DISCONNECTED
            self.onDisconnected()
        else:
            wasDisconnected = False

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
    
    @coroutine
    def _connected(self, initiating):
        self.logger.debug("Negociating protocol")
        conn = self.transport.connection
        try:
            name = yield negociateProtocol(conn, initiating)
        except TaskFailedError as e:
            type, val, tb = e.inner()
            if not isinstance(val, EOFError):
                self.logger.exception("Error while negociating protocol")
        else:
            self.logger.debug("Negociated protocol '%s'", name)
            self.messenger = AsyncMessenger(self.transport.connection)
            if self.service is not None:
                self.service.start()
            with self.__lock:
                waiters, self.startWaiters = self.startWaiters, []
            self._signalWaiters(waiters)
            while self.messenger is not None:
                try:
                    message = yield self.messenger.receiveMessage()
                except TaskFailedError as e:
                    type, val, tb = e.inner()
                    if not isinstance(val, EOFError):
                        self.logger.exception("Error while receiving a message")
                    message = None
                if message is None:
                    break
                else:
                    self.logger.debug("Received message: %s", message)
                    if self.service is not None:
                        self.deliverMessage(message, self.service)
        self.transport.disconnect()
    
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
                results = method(req)
                assert not isinstance(results, Future), "Request handler returned a future"
            except Exception as e:
                self.logger.exception("Error while executing request handler")
                self._sendErrorReponse(req, e)
            else:
                self.session.sendResponse(req, results)
        else:
            self.logger.error("Request handler '%s' not found" % req.tag)
            self._sendErrorReponse(req, NotImplementedError())
    
    def sendRequest(self, tag, params=None):
        """
        Send a request to the connected peer.
        """
        cont = Future()
        req = Request(tag, params)
        self.session.sendRequest(req).after(self.endSendRequest, cont)
        return cont
    
    def endSendRequest(self, prev, cont):
        try:
            resp = prev.result
        except Exception:
            cont.failed()
        else:
            if isinstance(resp.params, Mapping) and "error" in resp.params:
                error = resp.params["error"]
                cont.failed(Exception("The request failed: %s (%s)" %
                    (error["message"], error["type"])))
            else:
                cont.completed(resp)
    
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

class TcpMessenger(object):
    def __init__(self):
        self.pid = process.spawn(self._entry)
    
    def connect(self, addr):
        process.send(self.pid, ("connect", addr))
    
    def listen(self, addr):
        process.send(self.pid, ("listen", addr))
    
    def disconnect(self):
        process.send(self.pid, ("disconnect", ))

    def set_receiver(self, pid):
        process.send(self.pid, ("set-receiver", pid))
    
    def send(self, message):
        process.send(self.pid, ("send", message))

    def _entry(self):
        state = TcpProcessState()
        try:
            while True:
                m = process.receive()
                if match(("connect", None), m):
                    self._connect(m, state)
                elif match(("listen", None), m):
                    self._listen(m, state)
                elif match(("disconnect", ), m):
                    self._disconnect(m, state)
                elif match(("set-receiver", int), m):
                    state.receiver = m[1]
                elif match(("send", None), m):
                    self._send(m[1], state)
                elif match(("stop", ), m):
                    break
                else:
                    self._send(m, state)
        finally:
            self._close(state)

    def _connect(self, m, state):
        if state.connState != Transport.DISCONNECTED:
            state.logger.error("Invalid state '%i', should be DISCONNECTED", state.connState)
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        sock.bind(("0.0.0.0", 0))
        state.logger.info("Connecting to %s.", repr(m[1]))
        sock.connect(m[1])
        self._connected(state, sock, m[1], True)
    
    def _listen(self, m, state):
        if state.connState != Transport.DISCONNECTED:
            state.logger.error("Invalid state '%i', should be DISCONNECTED", state.connState)
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            sock.bind(m[1])
            sock.listen(1)
            state.logger.info("Waiting for connections on %s.", repr(m[1]))
            conn, remoteAddr = sock.accept()
        finally:
            sock.close()
        self._connected(state, conn, remoteAddr, False)

    def _connected(self, state, conn, remoteAddr, initiating):
        state.connState = Transport.CONNECTED
        state.conn = conn
        state.remoteAddr = remoteAddr
        state.logger.info("Connected to %s.", repr(remoteAddr))
        if state.receiver:
            process.send(state.receiver, Notification("connected", remoteAddr))
        stream = SocketWrapper(state.conn)
        name = negociateProtocol(stream, initiating)
        state.logger.info("Negociated protocol '%s'.", name)
        state.reader = messageReader(stream, name)
        state.writer = messageWriter(stream, name)
        if state.receiver:
            process.send(state.receiver, Notification("protocol-negociated", name))
            process.spawn(self._receiveMessages, stream, name, state.receiver)
    
    def _receiveMessages(self, f, protocol, receiverPid):
        reader = messageReader(f, protocol)
        log = process.logger()
        while True:
            m = reader.read()
            if m is None:
                log.info("End of stream.")
                break
            else:
                log.info("Received message: '%s'." % str(m))
            process.send(receiverPid, m)
    
    def _disconnect(self, m, state):
        self._close(state)
    
    def _close(self, state):
        if state.conn:
            state.logger.info("Disconnecting from %s." % repr(state.remoteAddr))
            # force threads blocked on recv (and send?) to return
            try:
                state.conn.shutdown(socket.SHUT_RDWR)
            except socket.error as e:
                if e.errno != os.errno.ENOTCONN:
                    raise
            except Exception:
                state.logger.exception("socket.shutdown() failed")
            # close the connection
            try:
                state.conn.close()
            except Exception:
                state.logger.exception("socket.close() failed")
            state.conn = None
            state.remoteAddr = None
            wasDisconnected = (state.connState == Transport.CONNECTED)
            state.connState = Transport.DISCONNECTED
        else:
            wasDisconnected = False
        # notifiy the receiver if the connection was closed
        if wasDisconnected and state.receiver:
            process.send(state.receiver, Notification("disconnected"))
    
    def _send(self, m, state):
        if state.connState != Transport.CONNECTED:
            state.logger.error("Not connected")
            return
        elif state.writer is None:
            state.logger.error("Session not started")
            return
        state.logger.info("Sending message: '%s'." % str(m))
        state.writer.write(m)

class TcpProcessState(object):
    def __init__(self):
        self.connState = Transport.DISCONNECTED
        self.conn = None
        self.remoteAddr = None
        self.receiver = None
        self.reader = None
        self.writer = None
        self.logger = process.logger()

class SocketWrapper(object):
    def __init__(self, sock):
        self.sock = sock
        self.read = sock.recv
        self.write = sock.send