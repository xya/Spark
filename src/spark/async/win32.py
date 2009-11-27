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
from ctypes import cast, byref, sizeof, POINTER, c_void_p, c_uint32, c_wchar_p

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
                ("hEvent", c_void_p),
                ("UserData", c_void_p)]

LP_OVERLAPPED = POINTER(OVERLAPPED)

INVALID_HANDLE_VALUE = c_void_p(-1)
HEAP_ZERO_MEMORY = 0x00000008

def _errorIfNull(ret):
    if not bool(ret):
        raise WinError()
    return ret

def _errorIfInvalid(ret):
    if ret == INVALID_HANDLE_VALUE.value:
        raise WinError()
    return ret

def allocOVERLAPPED():
    size = sizeof(OVERLAPPED)
    p = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, size)
    if p:
        return cast(p, LP_OVERLAPPED)
    else:
        return None

def freeOVERLAPPED(lpOver):
    p = cast(lpOver, c_void_p)
    if not HeapFree(GetProcessHeap(), 0, p):
        raise WinError()

kernel32 = windll.kernel32

# I/O completion ports functions
    
# HANDLE WINAPI CreateIoCompletionPort(
# __in      HANDLE FileHandle,
# __in_opt  HANDLE ExistingCompletionPort,
# __in      ULONG_PTR CompletionKey,
# __in      DWORD NumberOfConcurrentThreads
# );
CreateIoCompletionPort = kernel32.CreateIoCompletionPort
CreateIoCompletionPort.argtypes = [c_void_p, c_void_p, c_void_p, c_uint32]
CreateIoCompletionPort.restype = _errorIfNull
# BOOL WINAPI PostQueuedCompletionStatus(
#   __in      HANDLE CompletionPort,
#   __in      DWORD dwNumberOfBytesTransferred,
#   __in      ULONG_PTR dwCompletionKey,
#   __in_opt  LPOVERLAPPED lpOverlapped
# );
PostQueuedCompletionStatus = kernel32.PostQueuedCompletionStatus
PostQueuedCompletionStatus.argtypes = [c_void_p, c_uint32, c_void_p, LP_OVERLAPPED]
PostQueuedCompletionStatus.restype = _errorIfNull
# BOOL WINAPI GetQueuedCompletionStatus(
#   __in   HANDLE CompletionPort,
#   __out  LPDWORD lpNumberOfBytes,
#   __out  PULONG_PTR lpCompletionKey,
#   __out  LPOVERLAPPED *lpOverlapped,
#   __in   DWORD dwMilliseconds
# );
GetQueuedCompletionStatus = kernel32.GetQueuedCompletionStatus
GetQueuedCompletionStatus.argtypes = [c_void_p, POINTER(c_uint32),
    POINTER(c_void_p), POINTER(LP_OVERLAPPED), c_uint32]
GetQueuedCompletionStatus.restype = _errorIfNull


# BOOL WINAPI CloseHandle(
#   __in  HANDLE hObject
# );
CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [c_void_p]
CloseHandle.restype = _errorIfNull

# DWORD WINAPI GetLastError(void);
GetLastError = kernel32.GetLastError
GetLastError.argtypes = []
GetLastError.restype = c_uint32

# Heap functions

# HANDLE WINAPI GetProcessHeap(void);
GetProcessHeap = kernel32.GetProcessHeap
GetProcessHeap.argtypes = []
GetProcessHeap.restype = c_void_p
# LPVOID WINAPI HeapAlloc(
#   __in  HANDLE hHeap,
#   __in  DWORD dwFlags,
#   __in  SIZE_T dwBytes
# );
HeapAlloc = kernel32.HeapAlloc
HeapAlloc.argtypes = [c_void_p, c_uint32, c_void_p]
HeapAlloc.restype = _errorIfNull
# BOOL WINAPI HeapFree(
#   __in  HANDLE hHeap,
#   __in  DWORD dwFlags,
#   __in  LPVOID lpMem
# );
HeapFree = kernel32.HeapFree
HeapFree.argtypes = [c_void_p, c_uint32, c_void_p]
HeapFree.restype = _errorIfNull

# File I/O functions

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

CREATE_NEW = 1
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
OPEN_ALWAYS = 4
TRUNCATE_EXISTING = 5

FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OVERLAPPED = 0x40000000

# HANDLE WINAPI CreateFile(
#   __in      LPCTSTR lpFileName,
#   __in      DWORD dwDesiredAccess,
#   __in      DWORD dwShareMode,
#   __in_opt  LPSECURITY_ATTRIBUTES lpSecurityAttributes,
#   __in      DWORD dwCreationDisposition,
#   __in      DWORD dwFlagsAndAttributes,
#   __in_opt  HANDLE hTemplateFile
# );
CreateFile = kernel32.CreateFileW
CreateFile.argtypes = [c_wchar_p, c_uint32, c_uint32, c_void_p,
                       c_uint32, c_uint32, c_void_p]
CreateFile.restype = _errorIfInvalid

ERROR_IO_PENDING = 997

# BOOL WINAPI ReadFile(
#   __in         HANDLE hFile,
#   __out        LPVOID lpBuffer,
#   __in         DWORD nNumberOfBytesToRead,
#   __out_opt    LPDWORD lpNumberOfBytesRead,
#   __inout_opt  LPOVERLAPPED lpOverlapped
# );
ReadFile = kernel32.ReadFile
ReadFile.argtypes = [c_void_p, c_void_p, c_uint32, POINTER(c_uint32), LP_OVERLAPPED]
ReadFile.restype = c_uint32

# BOOL WINAPI WriteFile(
#   __in         HANDLE hFile,
#   __in         LPCVOID lpBuffer,
#   __in         DWORD nNumberOfBytesToWrite,
#   __out_opt    LPDWORD lpNumberOfBytesWritten,
#   __inout_opt  LPOVERLAPPED lpOverlapped
# );
WriteFile = kernel32.WriteFile
WriteFile.argtypes = [c_void_p, c_void_p, c_uint32, POINTER(c_uint32), LP_OVERLAPPED]
WriteFile.restype = c_uint32
