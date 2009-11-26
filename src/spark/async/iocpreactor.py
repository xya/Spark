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

__all__ = ["CompletionPortReactor"]

LOG_VERBOSE = 5

class CompletionPortReactor(Reactor):
    def __init__(self, name=None, lock=None):
        self.logger = logging.getLogger(name)
        if lock:
            self.lock = lock
        else:
            self.lock = threading.RLock()
        self.pending = {}
        self.onClosed = Delegate(self.lock)
        self.active = False
        self.cp = CompletionPort()
    
    def read(self, file, size):
        raise NotImplementedError()
    
    def write(self, file, data):
        raise NotImplementedError()
    
    def socket(self, family=None, type=None, proto=None):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        raise NotImplementedError()
    
    def connect(self, socket, address):
        raise NotImplementedError()
    
    def accept(self, socket):
        raise NotImplementedError()
    
    def callback(self, fun, *args, **kwargs):
        """ Submit a function to be called back on the reactor's thread. """
        if fun is None:
            raise TypeError("The function must not be None")
        self.cp.post(fun, *args, **kwargs)
    
    def launch_thread(self):
        """ Start a background I/O thread to run the reactor. """
        with self.lock:
            if self.active is False:
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
            else:
                return
        self.eventLoop()
    
    def submit(self, op):
        """
        Submit an I/O request to be performed asynchronously.
        Requests are not processed before either run() or launch_thread() is called.
        """
        pass
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        with self.lock:
            if self.active:
                self.cp.post(None)
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()
    
    def eventLoop(self):
        try:
            while True:
                self.logger.log(LOG_VERBOSE, "Waiting for GetQueuedCompletionStatus()")
                op = self.cp.wait()
                self.logger.log(LOG_VERBOSE, "Woke up from GetQueuedCompletionStatus()")
                if hasattr(op, 'func'):
                    self.handleCallback(op)
                elif hasattr(op, 'tag'):
                    self.handleIOCompletion(op)
                else:
                    break
        finally:
            self.cleanup()
    
    def cleanup(self):
        self.logger.debug("Reactor shutting down")
        with self.lock:
            self.active = False
            self.cp.close()
            self.cp = None
        try:
            self.onClosed()
        except Exception:
            self.logger.exception("onClosed() failed")
    
    def handleCallback(self, cb):
        self.logger.log(LOG_VERBOSE, "Invoking non-I/O callback %i" % cb.id)
        try:
            cb.func(*cb.args, **cb.kwargs)
        except Exception:
            self.logger.exception("Error in non-I/O callback")
    
    def handleIOCompletion(self, op):
        pass

from spark.async.win32 import *
from ctypes import cast, byref, POINTER, c_void_p, c_uint32

class CompletionPort(object):
    """ Wrapper for an I/O completion port """
    def __init__(self):
        """ Create a new completion port. """
        self.win32 = Win32()
        self.handle = self.win32.CreateIoCompletionPort(
            Win32.INVALID_HANDLE_VALUE, None, None, 0)
        self.lock = threading.RLock()
        self.callbacks = {}
    
    def close(self):
        """ Close the completion port. """
        if self.handle:
            self.win32.CloseHandle(self.handle)
            self.handle = c_void_p(0)
    
    def register(self, hFile):
        """ Register a file with the completion port and return its tag. """
        self.win32.CreateIoCompletionPort(hFile, self.handle, hFile, 0)
    
    def post(self, func, *args, **kwargs):
        """ Post a callback to the completion port. """
        # wish I could manually increase the refcount, to avoid the lock & dict
        with self.lock:
            cbData = (func, args, kwargs)
            cbID = id(cbData)
            self.callbacks[cbID] = cbData
        lpOver = self.win32.allocOVERLAPPED()
        lpOver.contents.Data.Pointer = cbID
        self.win32.PostQueuedCompletionStatus(self.handle, 0, None, lpOver)
    
    def wait(self):
        """ Wait for an operation to be finished and return it. """
        bytes = c_uint32()
        tag = c_void_p(0)
        lpOver = cast(0, LP_OVERLAPPED)
        self.win32.GetQueuedCompletionStatus(self.handle,
            byref(bytes), byref(tag), byref(lpOver), -1)
        if bool(tag):
            # IO operation, nothing special to do
            return IOOperation(tag, bytes, lpOver)
        else:
            # callback, need to free the OVERLAPPED struct
            cbID = lpOver.contents.Data.Pointer
            self.win32.freeOVERLAPPED(lpOver)
            with self.lock:
                cbData = self.callbacks.pop(cbID)
            if cbData[0] is None:
                return ShutdownRequest(cbID)
            else:
                return Callback(cbID, cbData[0], *cbData[1], **cbData[2])

class IOOperation(object):
    def __init__(self, tag, bytes, overlapped):
        self.tag = tag
        self.bytes = bytes
        self.overlapped = overlapped

class Callback(object):
    def __init__(self, id, func, *args, **kwargs):
        self.id = id
        self.func = func
        self.args = args
        self.kwargs = kwargs

class ShutdownRequest(object):
    def __init__(self, id):
        self.id = id