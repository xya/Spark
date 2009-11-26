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
    
    def register(self, file):
        """ Register the file to be used for asynchronous I/O operations. """
        pass
    
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
        raise NotImplementedError()
    
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
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

from ctypes import windll, WinError, Structure, Union
from ctypes import cast, byref, sizeof, POINTER, c_void_p, c_uint32

# typedef struct _OVERLAPPED {
#   ULONG_PTR Internal;
#   ULONG_PTR InternalHigh;
#   union {
#     struct {
#       DWORD Offset;
#       DWORD OffsetHigh;
#     } ;
#     PVOID Pointer;
#   } ;
#   HANDLE    hEvent;
# }OVERLAPPED, *LPOVERLAPPED;
class OVERLAPPED_offset(Structure):
    _fields_ = [("Low", c_uint32), ("High", c_uint32)]

class OVERLAPPED_data(Union):
    _fields_ = [("Offset", OVERLAPPED_offset), ("Pointer", c_void_p)]

class OVERLAPPED(Structure):
    _fields_ = [("Internal", POINTER(c_uint32)),
                ("InternalHigh", POINTER(c_uint32)),
                ("Data", OVERLAPPED_data),
                ("hEvent", c_void_p)]

LP_OVERLAPPED = POINTER(OVERLAPPED)

class Win32(object):
    """ Wrapper for Windows API functions """
    INVALID_HANDLE_VALUE = c_void_p(-1)
    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    PAGE_READWRITE = 0x04
    MEM_RELEASE = 0x8000
    HEAP_ZERO_MEMORY = 0x00000008
    
    def __init__(self):
        # HANDLE WINAPI CreateIoCompletionPort(
        # __in      HANDLE FileHandle,
        # __in_opt  HANDLE ExistingCompletionPort,
        # __in      ULONG_PTR CompletionKey,
        # __in      DWORD NumberOfConcurrentThreads
        # );
        self.CreateIoCompletionPort = windll.kernel32.CreateIoCompletionPort
        self.CreateIoCompletionPort.argtypes = [c_void_p, c_void_p,
                POINTER(c_uint32), c_uint32]
        self.CreateIoCompletionPort.restype = c_void_p
        # BOOL WINAPI PostQueuedCompletionStatus(
        #   __in      HANDLE CompletionPort,
        #   __in      DWORD dwNumberOfBytesTransferred,
        #   __in      ULONG_PTR dwCompletionKey,
        #   __in_opt  LPOVERLAPPED lpOverlapped
        # );
        self.PostQueuedCompletionStatus = windll.kernel32.PostQueuedCompletionStatus
        self.PostQueuedCompletionStatus.argtypes = [c_void_p, c_uint32,
                POINTER(c_uint32), LP_OVERLAPPED]
        self.PostQueuedCompletionStatus.restype = c_uint32
        # BOOL WINAPI GetQueuedCompletionStatus(
        #   __in   HANDLE CompletionPort,
        #   __out  LPDWORD lpNumberOfBytes,
        #   __out  PULONG_PTR lpCompletionKey,
        #   __out  LPOVERLAPPED *lpOverlapped,
        #   __in   DWORD dwMilliseconds
        # );
        self.GetQueuedCompletionStatus = windll.kernel32.GetQueuedCompletionStatus
        self.GetQueuedCompletionStatus.argtypes = [c_void_p, POINTER(c_uint32),
                POINTER(c_void_p), POINTER(LP_OVERLAPPED), c_uint32]
        self.GetQueuedCompletionStatus.restype = c_uint32
        #  LPVOID WINAPI VirtualAlloc(
        #   __in_opt  LPVOID lpAddress,
        #   __in      SIZE_T dwSize,
        #   __in      DWORD flAllocationType,
        #   __in      DWORD flProtect
        # );
        self.VirtualAlloc = windll.kernel32.VirtualAlloc
        self.VirtualAlloc.argtypes = [c_void_p, c_void_p, c_uint32, c_uint32]
        self.VirtualAlloc.restype = c_void_p
        # BOOL WINAPI VirtualFree(
        #  __in  LPVOID lpAddress,
        #  __in  SIZE_T dwSize,
        #  __in  DWORD dwFreeType
        # );
        self.VirtualFree = windll.kernel32.VirtualFree
        self.VirtualFree.argtypes = [c_void_p, c_void_p, c_uint32]
        self.VirtualFree.restype = c_uint32
        # HANDLE WINAPI GetProcessHeap(void);
        self.GetProcessHeap = windll.kernel32.GetProcessHeap
        self.GetProcessHeap.argtypes = []
        self.GetProcessHeap.restype = c_void_p
        # LPVOID WINAPI HeapAlloc(
        #   __in  HANDLE hHeap,
        #   __in  DWORD dwFlags,
        #   __in  SIZE_T dwBytes
        # );
        self.HeapAlloc = windll.kernel32.HeapAlloc
        self.HeapAlloc.argtypes = [c_void_p, c_uint32, c_void_p]
        self.HeapAlloc.restype = c_void_p
        # BOOL WINAPI HeapFree(
        #   __in  HANDLE hHeap,
        #   __in  DWORD dwFlags,
        #   __in  LPVOID lpMem
        # );
        self.HeapFree = windll.kernel32.HeapFree
        self.HeapFree.argtypes = [c_void_p, c_uint32, c_void_p]
        self.HeapFree.restype = c_void_p
    
    def allocOVERLAPPED(self):
        size = sizeof(OVERLAPPED)
        p = self.HeapAlloc(self.GetProcessHeap(), Win32.HEAP_ZERO_MEMORY, size)
        if p:
            return cast(p, LP_OVERLAPPED)
        else:
            return None
    
    def freeOVERLAPPED(self, lpOver):
        p = cast(lpOver, c_void_p)
        if not self.HeapFree(self.GetProcessHeap(), 0, p):
            raise WinError()

class CompletionPort(object):
    """ Wrapper for an I/O completion port """
    def __init__(self):
        """ Create a new completion port. """
        self.win32 = Win32()
        self.handle = self.win32.CreateIoCompletionPort(
            self.win32.INVALID_HANDLE_VALUE, None, None, 0)
        if not self.handle:
            raise WinError()
        self.lock = threading.RLock()
        self.callbacks = {}
    
    def register(self, hFile):
        """ Register a file with the completion port and return its tag. """
        ret = self.win32.CreateIoCompletionPort(hFile, self.handle, hFile, 0)
        if not self.handle:
            raise WinError()
    
    def post(self, func, *args, **kwargs):
        """ Post a callback to the completion port. """
        with self.lock:
            cbData = (func, args, kwargs)
            cbID = id(cbData)
            self.callbacks[cbID] = cbData
        lpOver = self.win32.allocOVERLAPPED()
        lpOver.contents.Data.Pointer = cbID
        ret = self.win32.PostQueuedCompletionStatus(self.handle, 0, None, lpOver)
        if not ret:
            raise WinError()
    
    def wait(self):
        """ Wait for an operation to be finished and return it. """
        bytes = c_uint32()
        tag = c_void_p(0)
        lpOver = cast(0, LP_OVERLAPPED)
        ret = self.win32.GetQueuedCompletionStatus(self.handle,
            byref(bytes), byref(tag), byref(lpOver), -1)
        if not ret:
            raise WinError()
        if bool(tag):
            # IO operation, nothing special to do
            return IOOperation(tag, bytes, lpOver)
        else:
            # callback, need to free the OVERLAPPED struct
            cbID = lpOver.contents.Data.Pointer
            self.win32.freeOVERLAPPED(lpOver)
            with self.lock:
                cbData = self.callbacks.pop(cbID)
            return Callback(cbData[0], *cbData[1], **cbData[2])

class IOOperation(object):
    def __init__(self, tag, bytes, overlapped):
        self.tag = tag
        self.bytes = bytes
        self.overlapped = overlapped

class Callback(object):
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self):
        self.func(*self.args, **self.kwargs)