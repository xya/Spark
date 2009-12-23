/*
 Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>

 This file is part of the Spark File-transfer Tool.

 Spark is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 Spark is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Spark; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

#ifndef PYTHON_IOCP_ASYNC_SOCKET
#define PYTHON_IOCP_ASYNC_SOCKET

#include "completionport.h"

extern PyTypeObject AsyncSocketType;

typedef struct
{
    PyObject_HEAD
    CompletionPort *port;
    int family;
    int type;
    int protocol;
    SOCKET socket;
    void *acceptEx;
    void *connectEx;
    void *getSockAddress;
} AsyncSocket;

void iocp_loadWinSock();
void iocp_unloadWinSock();

void AsyncSocket_dealloc(AsyncSocket *self);
PyObject * AsyncSocket_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
BOOL AsyncSocket_initExtensions(AsyncSocket *self);
BOOL AsyncSocket_bindDefault(AsyncSocket *self);
PyObject * AsyncSocket_bind(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_listen(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_beginConnect(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_beginAccept(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_beginRead(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_beginWrite(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_read(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_write(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_shutdown(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_fileno(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_close(AsyncSocket *self);
PyObject * AsyncSocket_enter(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_exit(AsyncSocket *self, PyObject *args);

PyObject * iocp_getResult_accept(DWORD error, DWORD bytes, PyObject *data, BOOL *success);
PyObject * iocp_getResult_connect(DWORD error, DWORD bytes, PyObject *data, BOOL *success);

struct sockaddr * AsyncSocket_stringToSockAddr(int family, char *host, int port, int *pAddrSize);
PyObject * AsyncSocket_sockAddrToString(int family, struct sockaddr *addr, int addrSize);

#endif