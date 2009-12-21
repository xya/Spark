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
from ctypes import WinError
from spark.async import Delegate
from spark.async.aio import Reactor
try:
    from spark.async import _iocp as iocp
    Future = iocp.Future
except ImportError:
    from spark.async import iocp, Future

__all__ = ["CompletionPortReactor"]

LOG_VERBOSE = 5

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
        raise NotImplementedError()
    
    def open(self, file, mode=None):
        """ Open a file that uses the reactor to do asynchronous I/O. """
        return self.cp.createFile(file, mode)
    
    def pipe(self):
        """ Create a pipe that uses the reactor to do asynchronous I/O. """
        return self.cp.createPipe()
    
    def send(self, fun, *args, **kwargs):
        """ Invoke a callable on the reactor's thread and return its result through a future. """
        if fun is None:
            raise TypeError("The callable must not be None")
        cont = Future()
        self.cp.post(iocp.OP_INVOKE, cont, (fun, args, kwargs))
        return cont
    
    def post(self, fun, *args, **kwargs):
        """ Submit a callable to be invoked on the reactor's thread later. """
        if fun is None:
            raise TypeError("The callable must not be None")
        self.cp.post(iocp.OP_INVOKE, None, (fun, args, kwargs))
    
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
                self.cp.post(iocp.OP_CLOSE)
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()
    
    def eventLoop(self):
        try:
            logging = self.logger.isEnabledFor(LOG_VERBOSE)
            while True:
                if logging:
                    self.logger.log(LOG_VERBOSE, "Waiting for GetQueuedCompletionStatus()")
                tag, error, bytes, opcode, cont, data = self.cp.wait()
                if logging:
                    self.logger.log(LOG_VERBOSE, "Woke up from GetQueuedCompletionStatus()")
                if opcode == iocp.OP_CLOSE:
                    break
                elif opcode == iocp.OP_INVOKE:
                    self.handleCallback(cont, *data)
                else:
                    self.cp.complete(tag, error, bytes, opcode, cont, data)
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
    
    def handleCallback(self, cont, func, args, kwargs):
        self.logger.log(LOG_VERBOSE, "Invoking non-I/O callback")
        if cont is None:
            try:
                func(*args, **kwargs)
            except Exception:
                self.logger.exception("Error in non-I/O callback")
        else:
            try:
                result = func(*args, **kwargs)
            except Exception:
                cont.failed()
            else:
                cont.completed(result)

# register the reactor
Reactor.addType(CompletionPortReactor)