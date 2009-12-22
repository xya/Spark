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
PyObject * AsyncSocket_close(AsyncSocket *self);
PyObject * AsyncSocket_enter(AsyncSocket *self, PyObject *args);
PyObject * AsyncSocket_exit(AsyncSocket *self, PyObject *args);
struct sockaddr * AsyncSocket_stringToSockAddr(int family, char *host, int port, int *pAddrSize);

#endif