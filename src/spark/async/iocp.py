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
import socket
import threading
import logging
from ctypes import WinError, cast, byref, POINTER, c_void_p, c_uint32, sizeof, create_string_buffer
from spark.async import win32

__all__ = ["CompletionPort", "ERROR_SUCCESS", "ERROR_BROKEN_PIPE"]

ERROR_SUCCESS = 0
ERROR_BROKEN_PIPE = 109

def _tuple_to_sockaddr_in(family, t):
    sockaddr = win32.sockaddr_in()
    sockaddr.sin_family = family
    sockaddr.sin_port = socket.htons(t[1])
    for i, c in enumerate(socket.inet_aton(t[0])):
        sockaddr.sin_addr[i] = ord(c)
    return sockaddr

def _sockaddr_in_to_tuple(sockaddr):
    port = socket.ntohs(sockaddr.sin_port)
    packed = "".join(chr(v) for v in sockaddr.sin_addr)
    address = socket.inet_ntoa(packed)
    return address, port

class Overlapped(object):
    """ Wrapper for Windows's OVERLAPPED structure. """
    def __init__(self, *data):
        self.id = id(self)
        self.data = data
        self.over = win32.allocOVERLAPPED()
        self.over.contents.UserData = self.id
    
    def address(self):
        return self.over
    
    def setOffset(self, offset):
        if self.over:
            self.over.contents.Data.Offset.Low = offset & 0x00000000ffffffff
            self.over.contents.Data.Offset.High = offset & 0xffffffff00000000
    
    def free(self):
        if self.over:
            win32.freeOVERLAPPED(self.over)
            self.over = None

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
    
    def memorize(self, overlapped):
        with self.lock:
            self.refs[overlapped.id] = overlapped
    
    def recall(self, id):
        with self.lock:
            if id in self.refs:
                return self.refs.pop(id)
            else:
                return None
    
    def post(self, *objs):
        """ Directly post the objects to the completion port. """
        ov = Overlapped(*objs)
        self.memorize(ov)
        win32.PostQueuedCompletionStatus(self.handle,
            0, win32.INVALID_HANDLE_VALUE, ov.address())
    
    def wait(self):
        """
        Wait for an operation to be finished and return a (ID, tag, bytes, objs)
        tuple containing the result. The OVERLAPPED structure is also freed. 
        """
        bytes = c_uint32()
        tag = c_void_p(0)
        lpOver = cast(0, win32.LP_OVERLAPPED)
        ret = win32.GetQueuedCompletionStatus(self.handle,
            byref(bytes), byref(tag), byref(lpOver), -1)
        if ret == 0:
            if lpOver.value is None:
                # Waiting for the completion of an operation failed
                raise WinError()
            else:
                # The I/O operation itself failed
                error = win32.GetLastError()
        else:
            error = ERROR_SUCCESS
        id = lpOver.contents.UserData
        ov = self.recall(id)
        ov.free()
        return ov.id, tag.value, error, bytes.value, ov.data
    
    def createFile(self, path, mode=None):
        if mode == "w":
            access = win32.GENERIC_WRITE
            creation = win32.CREATE_ALWAYS
        elif mode == "a":
            access = win32.FILE_APPEND_DATA
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
        handle = win32.CreateFile(path, access, 0, None, creation, flags, None)
        self.register(handle)
        return handle
    
    def closeFile(self, handle):
		return win32.CloseHandle(handle)
    
    def beginRead(self, op, handle, size, position, cont):
        buffer = create_string_buffer(size)
        over = Overlapped(op, buffer, cont)
        over.setOffset(position)
        self.memorize(over)
        ret = win32.ReadFile(handle, buffer, size, None, over.address())
        if not ret:
            error = win32.GetLastError()
            if error != win32.ERROR_IO_PENDING:
                over.free()
                raise WinError(error)

    def beginWrite(self, op, handle, data, position, cont):
        over = Overlapped(op, data, cont)
        over.setOffset(position)
        self.memorize(over)
        ret = win32.WriteFile(handle, data, len(data), None, over.address())
        if not ret:
            error = win32.GetLastError()
            if error != win32.ERROR_IO_PENDING:
                over.free()
                raise WinError(error)
    
    def beginAccept(self, op, handle, cont):
        raise NotImplementedError()
    
    def beginConnect(self, op, handle, address, cont):
        raise NotImplementedError()