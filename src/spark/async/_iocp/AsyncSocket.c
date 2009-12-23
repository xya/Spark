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

#include <Python.h>
#include <winsock2.h>
#include <mswsock.h>
#include <Ws2tcpip.h>
#include <windows.h>
#include "AsyncSocket.h"
#include "completionport.h"
#include "future.h"
#include "iocp.h"

static PyMethodDef AsyncSocket_methods[] =
{
    {"bind", (PyCFunction)AsyncSocket_bind, METH_VARARGS, "Bind the socket to an interface."},
    {"listen", (PyCFunction)AsyncSocket_listen, METH_VARARGS, "Put the socket in listening mode, waiting for new connections."},
    {"beginConnect", (PyCFunction)AsyncSocket_beginConnect, METH_VARARGS, "Start an asynchronous connect operation on the socket."},
    {"beginAccept", (PyCFunction)AsyncSocket_beginAccept, METH_VARARGS, "Start accepting an incoming connection on the socket."},
    {"close", (PyCFunction)AsyncSocket_close, METH_NOARGS, "Close the socket."},
    {"__enter__", (PyCFunction)AsyncSocket_enter, METH_VARARGS, ""},
    {"__exit__", (PyCFunction)AsyncSocket_exit, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyTypeObject AsyncSocketType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.AsyncSocket",                                    /*tp_name*/
    sizeof(AsyncSocket),                                    /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)AsyncSocket_dealloc,                        /*tp_dealloc*/
    0,                                                      /*tp_print*/
    0,                                                      /*tp_getattr*/
    0,                                                      /*tp_setattr*/
    0,                                                      /*tp_compare*/
    0,                                                      /*tp_repr*/
    0,                                                      /*tp_as_number*/
    0,                                                      /*tp_as_sequence*/
    0,                                                      /*tp_as_mapping*/
    0,                                                      /*tp_hash */
    0,                                                      /*tp_call*/
    0,                                                      /*tp_str*/
    0,                                                      /*tp_getattro*/
    0,                                                      /*tp_setattro*/
    0,                                                      /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,                                     /*tp_flags*/
    "AsyncSocket objects",                                  /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    AsyncSocket_methods,                                    /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    0,                                                      /* tp_init */
    0,                                                      /* tp_alloc */
    AsyncSocket_new,                                        /* tp_new */
};

void iocp_loadWinSock()
{
    WSAStartup(MAKEWORD(2, 2), NULL);
    Py_AtExit(iocp_unloadWinSock);
}

void iocp_unloadWinSock()
{
    WSACleanup();
}

void AsyncSocket_dealloc(AsyncSocket *self)
{
    AsyncSocket_close(self);
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * AsyncSocket_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *port;
    AsyncSocket *self;
    int sock_family, sock_type, sock_protocol;

    if(!PyArg_ParseTuple(args, "Olll", &port, &sock_family, &sock_type, &sock_protocol))
    {
        return NULL;
    }
    else if(!PyObject_TypeCheck(port, &CompletionPortType))
    {
        PyErr_SetString(PyExc_TypeError, "The first argument should be a completion port");
        return NULL;
    }
    else if((sock_family != AF_INET) && (sock_family != AF_INET6))
    {
        PyErr_SetString(PyExc_Exception, "Only IPv4 and IPv6 sockets are supported");
        return NULL;
    }

    self = (AsyncSocket *)type->tp_alloc(type, 0);
    if(self != NULL)
    {
        self->port = (CompletionPort *)port;
        self->family = sock_family;
        self->type = sock_type;
        self->protocol = sock_protocol;
        self->socket = WSASocket(sock_family, sock_type, sock_protocol, 
            NULL, 0, WSA_FLAG_OVERLAPPED);
        if(!AsyncSocket_initExtensions(self) 
            || !CompletionPort_registerFile(self->port, (HANDLE)self->socket))
        {
            closesocket(self->socket);
            Py_DECREF(self);
            return NULL;
        }
    }
    return (PyObject *)self;
}

BOOL AsyncSocket_initExtensions(AsyncSocket *self)
{
    int ret;
    DWORD dwBytes;
    GUID GuidAcceptEx = WSAID_ACCEPTEX;
    GUID GuidConnectEx = WSAID_CONNECTEX;
    GUID GuidGetSockAddress = WSAID_GETACCEPTEXSOCKADDRS;

    ret = WSAIoctl(self->socket, 
        SIO_GET_EXTENSION_FUNCTION_POINTER, 
        &GuidAcceptEx, 
        sizeof(GuidAcceptEx),
        &self->acceptEx, 
        sizeof(self->acceptEx), 
        &dwBytes, 
        NULL, 
        NULL);
    if(ret == SOCKET_ERROR)
        return FALSE;

    ret = WSAIoctl(self->socket, 
        SIO_GET_EXTENSION_FUNCTION_POINTER, 
        &GuidConnectEx, 
        sizeof(GuidConnectEx),
        &self->connectEx, 
        sizeof(self->connectEx), 
        &dwBytes, 
        NULL, 
        NULL);
    if(ret == SOCKET_ERROR)
        return FALSE;

    ret = WSAIoctl(self->socket, 
        SIO_GET_EXTENSION_FUNCTION_POINTER, 
        &GuidGetSockAddress, 
        sizeof(GuidGetSockAddress),
        &self->getSockAddress, 
        sizeof(self->getSockAddress), 
        &dwBytes, 
        NULL, 
        NULL);
    if(ret == SOCKET_ERROR)
        return FALSE;
    return TRUE;
}

BOOL AsyncSocket_bindDefault(AsyncSocket *self)
{
    struct sockaddr_in addr4;
    struct sockaddr_in6 addr6;

    if(self->family == AF_INET)
    {
        ZeroMemory(&addr4, sizeof(struct sockaddr_in));
        addr4.sin_family = AF_INET;
        if(bind(self->socket, &addr4, sizeof(struct sockaddr_in)) == SOCKET_ERROR)
        {
            iocp_lastwin32error("Could not bind the socket (%s)");
            return FALSE;
        }
        return TRUE;
    }
    else if(self->family == AF_INET6)
    {
        ZeroMemory(&addr6, sizeof(struct sockaddr_in6));
        addr6.sin6_family = AF_INET;
        if(bind(self->socket, &addr6, sizeof(struct sockaddr_in6)) == SOCKET_ERROR)
        {
            iocp_lastwin32error("Could not bind the socket (%s)");
            return FALSE;
        }
        return TRUE;
    }
    else
    {
        PyErr_SetString(PyExc_Exception, "Only IPv4 and IPv6 addresses are supported");
        return FALSE;
    }
}

PyObject * AsyncSocket_bind(AsyncSocket *self, PyObject *args)
{
    char *host;
    int port;
    struct sockaddr *addr;
    int addrSize, ret;

    if(!PyArg_ParseTuple(args, "(sl)", &host, &port))
        return NULL;

    addr = AsyncSocket_stringToSockAddr(self->family, host, port, &addrSize);
    if(!addr)
        return NULL;
    ret = bind(self->socket, addr, addrSize);
    free(addr);
    if(ret == SOCKET_ERROR)
    {
        iocp_lastwin32error("Could not bind the socket (%s)");
        return FALSE;
    }
    Py_RETURN_NONE;
}

PyObject * AsyncSocket_listen(AsyncSocket *self, PyObject *args)
{
    int backlog, ret;

    if(!PyArg_ParseTuple(args, "l", &backlog))
        return NULL;
    ret = listen(self->socket, backlog);
    if(ret == SOCKET_ERROR)
    {
        iocp_lastwin32error("Calling listen() failed (%s)");
        return FALSE;
    }
    Py_RETURN_NONE;
}

PyObject * AsyncSocket_beginAccept(AsyncSocket *self, PyObject *args)
{
    PyObject *connArgs, *conn, *cont, *buffer, *data;
    void *pBuffer;
    long addrSize;
    LPFN_ACCEPTEX acceptEx = (LPFN_ACCEPTEX)self->acceptEx;
    IOCPOverlapped *over = NULL;
    DWORD error;

    if(!PyArg_ParseTuple(args, ""))
        return NULL;

    connArgs = Py_BuildValue("Olll", self->port, self->family, self->type, self->protocol);
    if(!connArgs)
        return NULL;
    conn = PyObject_CallObject((PyObject *)&AsyncSocketType, connArgs);
    Py_DECREF(connArgs);
    if(!conn)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the socket for the connection");
        return NULL;
    }
    
    if(self->family == AF_INET)
        addrSize = sizeof(struct sockaddr_in) + 16;
    else
        addrSize = sizeof(struct sockaddr_in6) + 16;

    buffer = iocp_allocBuffer(addrSize * 2, &pBuffer);
    if(!buffer)
    {
        Py_DECREF(conn);
        return NULL;
    }

    data = Py_BuildValue("OOl", conn, buffer, addrSize);
    Py_DECREF(conn);
    Py_DECREF(buffer);
    if(!data)
        return NULL;

    cont = PyObject_CallObject((PyObject *)&FutureType, NULL);
    if(!cont)
    {
        Py_DECREF(data);
        PyErr_SetString(PyExc_Exception, "Could not create the continuation");
        return NULL;
    }

    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->opcode = OP_ACCEPT;
    Py_INCREF(cont);
    over->cont = cont;
    over->data = data;
    if(!acceptEx(self->socket, ((AsyncSocket *)conn)->socket, pBuffer, 0, 
        (DWORD)addrSize, (DWORD)addrSize, NULL, (LPOVERLAPPED)over))
    {
        error = WSAGetLastError();
        if((error != ERROR_IO_PENDING) && (error != WSA_IO_PENDING))
        {
            iocp_win32error(error, NULL);
            // 2 references to cont, one for the return value and one for wait()
            Py_DECREF(over->cont);
            Py_DECREF(over->cont);
            Py_DECREF(over->data);
            free(over);
            return NULL;
        }
    }
    return cont;
}

PyObject * AsyncSocket_beginConnect(AsyncSocket *self, PyObject *args)
{
    PyObject *cont;
    char *host;
    int port;
    struct sockaddr *addr;
    int addrSize;
    LPFN_CONNECTEX connectEx = (LPFN_CONNECTEX)self->connectEx;
    IOCPOverlapped *over = NULL;
    DWORD error;

    if(!PyArg_ParseTuple(args, "(sl)", &host, &port))
        return NULL;
    else if(!AsyncSocket_bindDefault(self))
        return NULL;

    addr = AsyncSocket_stringToSockAddr(self->family, host, port, &addrSize);
    if(!addr)
        return NULL;

    cont = PyObject_CallObject((PyObject *)&FutureType, NULL);
    if(!cont)
    {
        free(addr);
        PyErr_SetString(PyExc_Exception, "Could not create the continuation");
        return NULL;
    }

    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->opcode = OP_CONNECT;
    Py_INCREF(cont);
    over->cont = cont;
    Py_INCREF(args);
    over->data = args;
    if(!connectEx(self->socket, addr, addrSize, NULL, 0, NULL, (LPOVERLAPPED)over))
    {
        error = WSAGetLastError();
        if((error != ERROR_IO_PENDING) && (error != WSA_IO_PENDING))
        {
            iocp_win32error(error, NULL);
            free(addr);
            // 2 references to cont, one for the return value and one for wait()
            Py_DECREF(over->cont);
            Py_DECREF(over->cont);
            Py_DECREF(over->data);
            free(over);
            return NULL;
        }
    }
    // does addr has to stay alive until the completion is posted?
    free(addr);
    return cont;
}

PyObject * AsyncSocket_close(AsyncSocket *self)
{
    if(self->socket)
    {
        closesocket(self->socket);
        self->socket = 0;
    }
    Py_RETURN_NONE;
}

PyObject * AsyncSocket_enter(AsyncSocket *self, PyObject *args)
{
    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    Py_INCREF(self);
    return self;
}

PyObject * AsyncSocket_exit(AsyncSocket *self, PyObject *args)
{
    PyObject *type, *val, *tb, *ret;
    if(!PyArg_ParseTuple(args, "OOO", &type, &val, &tb))
        return NULL;
    
    ret = AsyncSocket_close(self);
    if(!ret)
        return NULL;
    Py_DECREF(ret);
    Py_RETURN_NONE;
}

PyObject * iocp_getResult_accept(DWORD error, DWORD bytes, PyObject *data, BOOL *success)
{
    PyObject *buffer, *addressTuple, *ret;
    AsyncSocket *conn;
    void *pBuffer;
    Py_ssize_t bufferSize;
    long addrSize;
    LPFN_GETACCEPTEXSOCKADDRS getSockAddress;
    struct sockaddr *localAddr, *remoteAddr;
    int localSize, remoteSize;

    if(error == ERROR_SUCCESS)
    {
        /*
        if(setsockopt(self->socket, SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, NULL, 0) == SOCKET_ERROR)
        {
            success = FALSE;
            iocp_lastwin32error("Error while updating the socket after ConnectEx (%s)");
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
        */
        
        conn = (AsyncSocket *)PyTuple_GetItem(data, 0);
        buffer = PyTuple_GetItem(data, 1);
        if((PyObject_AsReadBuffer(buffer, &pBuffer, &bufferSize) != 0) || (bufferSize <= 0))
        {
            *success = FALSE;
            PyErr_SetString(PyExc_Exception, "Couldn't access the buffer for reading");
            return NULL;
        }
        addrSize = PyInt_AsLong(PyTuple_GetItem(data, 2));
        getSockAddress = (LPFN_GETACCEPTEXSOCKADDRS)conn->getSockAddress;
        getSockAddress(pBuffer, 0, addrSize, addrSize, 
            &localAddr, &localSize, &remoteAddr, &remoteSize);
        addressTuple = AsyncSocket_sockAddrToString(conn->family, remoteAddr, remoteSize);
        if(!addressTuple)
        {
            *success = FALSE;
            return NULL;
        }
        ret = Py_BuildValue("OO", conn, addressTuple);
        Py_DECREF(addressTuple);
        if(!ret)
        {
            *success = FALSE;
            return NULL;
        }
        *success = TRUE;
        return ret;
    }
    else
    {
        *success = FALSE;
        iocp_win32error(error, "The accept operation failed (%s)");
        return iocp_fetchException();
    }
}

PyObject * iocp_getResult_connect(DWORD error, DWORD bytes, PyObject *data, BOOL *success)
{
    if(error == ERROR_SUCCESS)
    {
        /*
        if(setsockopt(self->socket, SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, NULL, 0) == SOCKET_ERROR)
        {
            success = FALSE;
            iocp_lastwin32error("Error while updating the socket after ConnectEx (%s)");
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
        */
        *success = TRUE;
        Py_INCREF(data);
        return data;
    }
    else
    {
        *success = FALSE;
        iocp_win32error(error, "The connect operation failed (%s)");
        return iocp_fetchException();
    }
}

struct sockaddr * AsyncSocket_stringToSockAddr(int family, char *host, int port, int *pAddrSize)
{
    struct sockaddr_in *addr4;
    struct sockaddr_in6 *addr6;

    if((port < 0x0000) || (port > 0xffff))
    {
        PyErr_SetString(PyExc_TypeError, "The port should be in [0,65535]");
        return NULL;
    }
    else if((family != AF_INET) && (family != AF_INET6))
    {
        PyErr_SetString(PyExc_Exception, "Only IPv4 and IPv6 addresses are supported");
        return NULL;
    }
    else if(!pAddrSize)
    {
        PyErr_SetString(PyExc_Exception, "pAddrSize must not be NULL");
        return NULL;
    }
    
    if(family == AF_INET)
    {
        *pAddrSize = sizeof(struct sockaddr_in);
        addr4 = (struct sockaddr_in *)malloc(*pAddrSize);
        if(!addr4)
        {
            PyErr_SetString(PyExc_Exception, "Could not allocate address");
            return NULL;
        }
        else if(WSAStringToAddressA(host, AF_INET, NULL, addr4, pAddrSize) == SOCKET_ERROR)
        {
            iocp_lastwin32error(NULL);
            return NULL;
        }
        else
        {
            addr4->sin_port = htons(port);
            return (struct sockaddr *)addr4;
        }
    }
    else
    {
        *pAddrSize = sizeof(struct sockaddr_in6);
        addr6 = (struct sockaddr_in6 *)malloc(*pAddrSize);
        if(!addr6)
        {
            PyErr_SetString(PyExc_Exception, "Could not allocate address");
            return NULL;
        }
        else if(WSAStringToAddressA(host, AF_INET6, NULL, addr6, pAddrSize) == SOCKET_ERROR)
        {
            iocp_lastwin32error(NULL);
            return NULL;
        }
        else
        {
            addr6->sin6_port = htons(port);
            return (struct sockaddr *)addr6;
        }
    }
}

// Convert a socket address to a (address string, port numner) tuple
PyObject * AsyncSocket_sockAddrToString(int family, struct sockaddr *addr, int addrSize)
{
    DWORD error, port, stringSize = 0;
    char dummy = '\0';
    char *addressString = NULL;
    PyObject *tuple;

    if(!addr)
    {
        PyErr_SetString(PyExc_Exception, "addr must not be NULL");
        return NULL;
    }
    else if(family == AF_INET)
    {
        port = ntohs(((struct sockaddr_in *)addr)->sin_port);
    }
    else if(family == AF_INET6)
    {
        port = ntohs(((struct sockaddr_in6 *)addr)->sin6_port);
    }
    else
    {
        PyErr_SetString(PyExc_Exception, "Only IPv4 and IPv6 addresses are supported");
        return NULL;
    }
    
    WSAAddressToStringA(addr, addrSize, NULL, &dummy, &stringSize);
    if(stringSize <= 0)
    {
        iocp_win32error(error, "Could not translate the address to a string (%s)");
        return NULL;
    }
    addressString = (char *)malloc(stringSize);
    if(!addressString)
    {
        PyErr_SetString(PyExc_MemoryError, "Could not allocate memory for the address");
        return NULL;
    }
    else if(WSAAddressToStringA(addr, addrSize, NULL, addressString, &stringSize) == SOCKET_ERROR)
    {
        iocp_lastwin32error("Could not translate the address to a string (%s)");
        free(addressString);
        return NULL;
    }
    tuple = Py_BuildValue("(sl)", addressString, port);
    free(addressString);
    return tuple;
}
