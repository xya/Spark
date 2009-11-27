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
from ctypes import WinError, cast, byref, POINTER, c_void_p, c_uint32, create_string_buffer
from spark.async import Future, Delegate
from spark.async.aio import Reactor
from spark.async import win32

__all__ = ["CompletionPortReactor"]

LOG_VERBOSE = 5

OP_CALLBACK = 0
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
        self.cp = CompletionPort()
    
    def read(self, file, size):
        if hasattr(file, "fileno"):
            handle = file.fileno()
        else:
            handle = file
        cont = Future()
        buffer = create_string_buffer(size)
        lpOver = self.cp.overlapped(OP_READ, buffer, cont)
        ret = win32.ReadFile(handle, buffer, size, None, lpOver)
        if not ret:
            error = win32.GetLastError()
            if error != win32.ERROR_IO_PENDING:
                raise WinError(error)
        return cont
    
    def write(self, file, data):
        if hasattr(file, "fileno"):
            handle = file.fileno()
        else:
            handle = file
        cont = Future()
        lpOver = self.reactor.cp.overlapped(OP_WRITE, cont)
        ret = win32.WriteFile(handle, data, len(data), None, lpOver)
        if not ret:
            error = win32.GetLastError()
            if error != win32.ERROR_IO_PENDING:
                raise WinError(error)
        return cont
    
    def socket(self, family=None, type=None, proto=None):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        raise NotImplementedError()
    
    def open(self, file, mode=None):
        """ Open a file that uses the reactor to do asynchronous I/O. """
        return OverlappedFile.open(self, file, mode)
    
    def pipe(self):
        """ Create a pipe that uses the reactor to do asynchronous I/O. """
        raise NotImplementedError()
    
    def connect(self, socket, address):
        raise NotImplementedError()
    
    def accept(self, socket):
        raise NotImplementedError()
    
    def callback(self, fun, *args, **kwargs):
        """ Submit a function to be called back on the reactor's thread. """
        if fun is None:
            raise TypeError("The function must not be None")
        self.cp.post(OP_CALLBACK, fun, args, kwargs)
    
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
                elif data[0] == OP_CALLBACK:
                    self.handleCallback(id, data[1], data[2], data[3])
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
    
    def handleCallback(self, id, func, args, kwargs):
        self.logger.log(LOG_VERBOSE, "Invoking non-I/O callback %s" % hex(id))
        try:
            func(*args, **kwargs)
        except Exception:
            self.logger.exception("Error in non-I/O callback %s" % hex(id))
    
    def handleIOCompletion(self, id, tag, bytes, data):
        op = data[0]
        if op == OP_READ:
            op, buffer, cont = data
            cont.completed(buffer.raw)
        elif op == OP_WRITE:
            op, cont = data
            cont.completed()

class OverlappedFile(object):
    """ File-like object that uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, handle):
        self.reactor = reactor
        self.handle = handle
    
    @property
    def fileno(self):
        return self.handle
    
    @classmethod
    def open(cls, reactor, file, mode=None):
        if mode == "w":
            access = win32.GENERIC_WRITE
            creation = win32.CREATE_ALWAYS
        elif mode == "a":
            access = win32.GENERIC_WRITE
            creation = win32.OPEN_ALWAYS
        elif mode == "r+":
            access = win32.GENERIC_READ | win32.GENERIC_WRITE
            creation = win32.OPEN_EXISTING
        elif mode == "w+":
            access = win32.GENERIC_READ | win32.GENERIC_WRITE
            creation =  win32.CREATE_ALWAYS
        elif mode == "a+":
            access = win32.GENERIC_READ | win32.GENERIC_WRITE
            creation = win32.OPEN_ALWAYS
        else:
            access = win32.GENERIC_READ
            creation = win32.OPEN_EXISTING
        flags = win32.FILE_FLAG_OVERLAPPED | win32.FILE_ATTRIBUTE_NORMAL
        handle = win32.CreateFile(file, access, 0, None, creation, flags, None)
        reactor.cp.register(handle)
        return cls(reactor, handle)
    
    def beginRead(self, size):
        return self.reactor.read(self.handle, size)
    
    def beginWrite(self, data):
        return self.reactor.write(self.handle, data)
    
    def read(self, size):
        raise NotImplementedError()
    
    def write(self, data):
        raise NotImplementedError()
    
    def close(self):
        if self.handle:
            win32.CloseHandle(self.handle)
            self.handle = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

class CompletionPort(object):
    """ Wrapper for an I/O completion port """
    def __init__(self):
        """ Create a new completion port. """
        self.handle = win32.CreateIoCompletionPort(
            win32.INVALID_HANDLE_VALUE, None, None, 0)
        self.lock = threading.RLock()
        self.refs = {}
    
    def close(self):
        """ Close the completion port. """
        if self.handle:
            win32.CloseHandle(self.handle)
            self.handle = c_void_p(0)
    
    def register(self, hFile):
        """ Register a file with the completion port and return its tag. """
        win32.CreateIoCompletionPort(hFile, self.handle, hFile, 0)
    
    def overlapped(self, *objs):
        """
        Create an OVERLAPPED struct, eventually wrapping some objects,
        and return a pointer to the struct. The objects will be returned,
        and the structure freed by wait().
        """
        # wish I could manually increase the refcount, to avoid the lock & dict
        if len(objs) > 0:
            with self.lock:
                refData = tuple(objs)
                refID = id(refData)
                self.refs[refID] = refData
        else:
            refID = 0
        lpOver = win32.allocOVERLAPPED()
        lpOver.contents.UserData = refID
        return lpOver
    
    def post(self, *objs):
        """ Directly post the objects to the completion port. """
        win32.PostQueuedCompletionStatus(self.handle,
            0, win32.INVALID_HANDLE_VALUE, self.overlapped(*objs))
    
    def wait(self):
        """
        Wait for an operation to be finished and return a (ID, tag, bytes, objs)
        tuple containing the result. The OVERLAPPED structure is also freed. 
        """
        bytes = c_uint32()
        tag = c_void_p(0)
        lpOver = cast(0, win32.LP_OVERLAPPED)
        win32.GetQueuedCompletionStatus(self.handle,
            byref(bytes), byref(tag), byref(lpOver), -1)
        refID = lpOver.contents.UserData
        win32.freeOVERLAPPED(lpOver)
        if refID > 0:
            with self.lock:
                userData = self.refs.pop(refID)
        else:
            userData = ()
        return refID, tag.value, bytes.value, userData