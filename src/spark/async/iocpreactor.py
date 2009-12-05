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
import threading
import socket
import logging
from spark.async import Future, Delegate
from spark.async.aio import Reactor
try:
    from spark.async import _iocp as iocp
except ImportError:
    from spark.async import iocp

__all__ = ["CompletionPortReactor"]

LOG_VERBOSE = 5

OP_INVOKE = 0
OP_READ = 1
OP_WRITE = 2
OP_CONNECT = 3
OP_ACCEPT = 4

class CompletionPortReactor(Reactor):
    def __init__(self, name=None, lock=None):
        self.logger = logging.getLogger(name)
        if lock:
            self.lock = lock
        else:
            self.lock = threading.RLock()
        self.onClosed = Delegate(self.lock)
        self.active = False
        self.closed = False
        self.cp = iocp.CompletionPort()
    
    def socket(self, family, type, proto):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        return OverlappedSocket(self, family, type, proto)
    
    def open(self, file, mode=None):
        """ Open a file that uses the reactor to do asynchronous I/O. """
        return OverlappedFile(self, self.cp.createFile(file, mode))
    
    def pipe(self):
        """ Create a pipe that uses the reactor to do asynchronous I/O. """
        readHandle, writeHandle = self.cp.createPipe()
        return (OverlappedFile(self, readHandle), OverlappedFile(self, writeHandle))
    
    def send(self, fun, *args, **kwargs):
        """ Invoke a callable on the reactor's thread and return its result through a future. """
        if fun is None:
            raise TypeError("The callable must not be None")
        cont = Future()
        self.cp.post(OP_INVOKE, cont, fun, args, kwargs)
        return cont
    
    def post(self, fun, *args, **kwargs):
        """ Submit a callable to be invoked on the reactor's thread later. """
        if fun is None:
            raise TypeError("The callable must not be None")
        self.cp.post(OP_INVOKE, None, fun, args, kwargs)
    
    def launch_thread(self):
        """ Start a background I/O thread to run the reactor. """
        with self.lock:
            if self.active is False:
                if self.closed:
                    raise Exception("The reactor has been closed")
                self.active = True
                t = threading.Thread(target=self.eventLoop, name="I/O thread")
                t.daemon = True
                t.start()
                return True
            else:
                return False
    
    def run(self):
        """ Run the reactor on the current thread. """
        with self.lock:
            if self.active is False:
                self.active = True
            elif self.closed:
                raise Exception("The reactor has been closed")
            else:
                return
        self.eventLoop()
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        with self.lock:
            if self.active:
                self.cp.post()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()
    
    def eventLoop(self):
        try:
            while True:
                self.logger.log(LOG_VERBOSE, "Waiting for GetQueuedCompletionStatus()")
                id, tag, bytes, data = self.cp.wait()
                self.logger.log(LOG_VERBOSE, "Woke up from GetQueuedCompletionStatus()")
                if len(data) == 0:
                    break
                elif data[0] == OP_INVOKE:
                    self.handleCallback(id, *data[1:])
                else:
                    self.handleIOCompletion(id, tag, bytes, data)
        finally:
            self.cleanup()
    
    def cleanup(self):
        self.logger.debug("Reactor shutting down")
        with self.lock:
            self.active = False
            self.cp.close()
            self.closed = True
        try:
            self.onClosed()
        except Exception:
            self.logger.exception("onClosed() failed")
    
    def handleCallback(self, id, cont, func, args, kwargs):
        self.logger.log(LOG_VERBOSE, "Invoking non-I/O callback %s" % hex(id))
        if cont is None:
            try:
                func(*args, **kwargs)
            except Exception:
                self.logger.exception("Error in non-I/O callback %s" % hex(id))
        else:
            cont.run(func, *args, **kwargs)
    
    def handleIOCompletion(self, id, tag, bytes, data):
        op = data[0]
        if op == OP_READ:
            op, buffer, cont = data
            cont.completed(buffer[0:bytes])
        elif op == OP_WRITE:
            op, buffer, cont = data
            cont.completed()
        elif op == OP_ACCEPT:
            op, addrpair, conn, cont = data
            remoteAddr = _sockaddr_in_to_tuple(addrpair[1])
            cont.completed((conn, remoteAddr))
        elif op == OP_CONNECT:
            op, sockaddr, conn, cont = data
            remoteAddr = _sockaddr_in_to_tuple(sockaddr)
            cont.completed((conn, remoteAddr))

class OverlappedFile(object):
    """ File-like object that uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, handle):
        self.reactor = reactor
        self.handle = handle
    
    @property
    def fileno(self):
        return self.handle
    
    def beginRead(self, size, position=0):
        cont = Future()
        self.reactor.cp.beginRead(OP_READ, self.handle, size, position, cont)
        return cont
    
    def beginWrite(self, data, position=0):
        cont = Future()
        self.reactor.cp.beginWrite(OP_WRITE, self.handle, data, position, cont)
        return cont
    
    def read(self, size, position=0):
        return self.beginRead(size, position).result
    
    def write(self, data, position=0):
        return self.beginWrite(data, position).result
    
    def close(self):
        if self.handle:
            self.reactor.cp.closeFile(self.handle)
            self.handle = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

class OverlappedSocket(object):
    """ File-like wrapper for a socket. Uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, family, type, proto):
        self.reactor = reactor
        self.family = family
        self.type = type
        self.proto = proto
        self.socket = socket.socket(self.family, self.type, self.proto)
    
    @property
    def fileno(self):
        return self.socket.fileno()
    
    def bind(self, address):
        return self.socket.bind(address)
    
    def listen(self, backlog=1):
        return self.socket.listen(backlog)
    
    def beginAccept(self):
        cont = Future()
        self.reactor.cp.beginAccept(OP_ACCEPT, self.fileno, cont)
        return cont
    
    def beginConnect(self, address):
        cont = Future()
        self.reactor.cp.beginAccept(OP_CONNECT, self.fileno, address, cont)
        return cont
    
    def beginRead(self, size):
        cont = Future()
        iocp.beginRead(self.reactor.cp, OP_READ, self.socket.fileno, size, 0, cont)
        return cont
    
    def beginWrite(self, data):
        cont = Future()
        iocp.beginWrite(self.reactor.cp, OP_WRITE, self.socket.fileno, data, 0, cont)
        return cont
    
    def shutdown(self, how):
        return self.socket.shutdown(how)
    
    def close(self):
        return self.socket.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()