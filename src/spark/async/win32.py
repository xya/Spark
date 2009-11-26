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

from ctypes import windll, WinError, Structure, Union
from ctypes import cast, byref, sizeof, POINTER, c_void_p, c_uint32

__all__ = ["Win32", "OVERLAPPED", "LP_OVERLAPPED"]

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
        self.CreateIoCompletionPort.restype = self._errorIfNull
        # BOOL WINAPI PostQueuedCompletionStatus(
        #   __in      HANDLE CompletionPort,
        #   __in      DWORD dwNumberOfBytesTransferred,
        #   __in      ULONG_PTR dwCompletionKey,
        #   __in_opt  LPOVERLAPPED lpOverlapped
        # );
        self.PostQueuedCompletionStatus = windll.kernel32.PostQueuedCompletionStatus
        self.PostQueuedCompletionStatus.argtypes = [c_void_p, c_uint32,
                POINTER(c_uint32), LP_OVERLAPPED]
        self.PostQueuedCompletionStatus.restype = self._errorIfNull
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
        self.GetQueuedCompletionStatus.restype = self._errorIfNull
        # BOOL WINAPI CloseHandle(
        #   __in  HANDLE hObject
        # );
        self.CloseHandle = windll.kernel32.CloseHandle
        self.CloseHandle.argtypes = [c_void_p]
        self.CloseHandle.restype = self._errorIfNull
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
        self.HeapAlloc.restype = self._errorIfNull
        # BOOL WINAPI HeapFree(
        #   __in  HANDLE hHeap,
        #   __in  DWORD dwFlags,
        #   __in  LPVOID lpMem
        # );
        self.HeapFree = windll.kernel32.HeapFree
        self.HeapFree.argtypes = [c_void_p, c_uint32, c_void_p]
        self.HeapFree.restype = self._errorIfNull
    
    def _errorIfNull(self, ret):
        if not bool(ret):
            raise WinError()
        return ret
    
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