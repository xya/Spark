#include <Python.h>
#include <windows.h>
#include "completionport.h"
#include "AsyncFile.h"
#include "AsyncSocket.h"
#include "iocp.h"

static PyMethodDef CompletionPort_methods[] =
{
    {"close", (PyCFunction)CompletionPort_close, METH_VARARGS, 
        "Close the completion port."},
    {"throw", (PyCFunction)CompletionPort_throw, METH_VARARGS,
        "Post an exception to the completion port. It will be raised by wait()."},
    {"invokeLater", (PyCFunction)CompletionPort_invokeLater, METH_VARARGS, 
        "Post a callable to the completion port. It will be invoked by wait()."},
    {"wait",  (PyCFunction)CompletionPort_wait, METH_VARARGS, 
        "Wait for an operation to be finished and return a (success, result, cont) tuple describing its outcome."},
    {"createFile", (PyCFunction)CompletionPort_createFile, METH_VARARGS, 
        "Create or open a file in asynchronous mode."},
    {"createPipe", (PyCFunction)CompletionPort_createPipe, METH_VARARGS, 
        "Create an asynchronous pipe."},
    {"createSocket", (PyCFunction)CompletionPort_createSocket, METH_VARARGS, 
        "Create a socket in asynchronous mode."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyTypeObject CompletionPortType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.CompletionPort",                                 /*tp_name*/
    sizeof(CompletionPort),                                 /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)CompletionPort_dealloc,                     /*tp_dealloc*/
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
    "Completion port objects",                              /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    CompletionPort_methods,                                 /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    (initproc)CompletionPort_init,                          /* tp_init */
    0,                                                      /* tp_alloc */
    CompletionPort_new,                                     /* tp_new */
};

void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset)
{
    ov->Offset = (DWORD)((__int64)offset & (__int64)0x00000000ffffffff);
    ov->OffsetHigh = (DWORD)(((__int64)offset & (__int64)0xffffffff00000000) >> 32);
}

void CompletionPort_dealloc(CompletionPort* self)
{
    if(self->hPort)
    {
        CloseHandle(self->hPort);
        self->hPort = 0;
    }
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * CompletionPort_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    CompletionPort *self = (CompletionPort *)type->tp_alloc(type, 0);
    if(self != NULL)
        self->hPort = 0;
    return (PyObject *)self;
}

int CompletionPort_init(CompletionPort *self, PyObject *args, PyObject *kwds)
{
    if(!PyArg_ParseTuple(args, ""))
        return -1;
    self->hPort = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, (ULONG_PTR)NULL, 0);
    if(!self->hPort)
        iocp_lastwin32error("Could not create completion port (%s)");
    return 0;
}

PyObject * CompletionPort_close(CompletionPort *self, PyObject *args)
{
    if(!PyArg_ParseTuple(args, ""))
        return NULL;

    if(self->hPort)
    {
        CloseHandle(self->hPort);
        self->hPort = 0;
    }
    Py_RETURN_NONE;
}

PyObject * CompletionPort_post(CompletionPort *self, DWORD opcode, PyObject *cont, PyObject *data)
{
    IOCPOverlapped *over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    if(!over)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the overlapped object");
        return NULL;
    }

    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->opcode = opcode;
    Py_INCREF(cont);
    over->cont = cont;
    Py_INCREF(data);
    over->data = data;
    
    // don't decrement cont and data's refcount, so they remain alive until wait() returns
    PostQueuedCompletionStatus(self->hPort, 0, 
        (ULONG_PTR)INVALID_HANDLE_VALUE, (LPOVERLAPPED)over);
    Py_RETURN_NONE;
}

PyObject * CompletionPort_invokeLater(CompletionPort *self, PyObject *args)
{
    PyObject *func, *func_args, *func_kw, *cont = Py_None;
    PyObject *postArgs, *ret;
    if(!PyArg_ParseTuple(args, "OOO|O", &func, &func_args, &func_kw, &cont))
    {
        return NULL;
    }
    else if(!PyCallable_Check(func))
    {
        PyErr_SetString(PyExc_TypeError, "The first argument should be a callable");
    }

    postArgs = Py_BuildValue("OOO", func, func_args, func_kw);
    ret = CompletionPort_post(self, OP_INVOKE, cont, postArgs);
    Py_DECREF(postArgs);
    return ret;
}

PyObject * CompletionPort_throw(CompletionPort *self, PyObject *args)
{
    PyObject *exc;
    if(!PyArg_ParseTuple(args, "O", &exc))
        return NULL;
    return CompletionPort_post(self, OP_THROW, Py_None, exc);
}

PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args)
{
    BOOL success = FALSE;
    DWORD bytes = 0, error = ERROR_SUCCESS;
    ULONG_PTR tag = 0;
    IOCPOverlapped *over = NULL;
    PyObject *result = NULL;

    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
    success = GetQueuedCompletionStatus(self->hPort, &bytes, &tag, (LPOVERLAPPED *)&over, -1);
    Py_END_ALLOW_THREADS
    if(!success)
    {
        if(over == NULL)
        {
            // Waiting for the completion of an operation failed
            iocp_lastwin32error("Waiting for an operation's completion failed (%s)");
            return NULL;
        }
        else
        {
            // The I/O operation itself failed
            error = GetLastError();
        }
    }

    result = CompletionPort_getResult(self, tag, error, bytes, over->opcode, over->cont, over->data);
    // INCREF was done in beginRead/beginWrite/post to keep these alive
    Py_DECREF(over->cont);
    Py_DECREF(over->data);
    free(over);
    return result;
}

PyObject * CompletionPort_getResult(CompletionPort *self, ULONG_PTR tag, 
        DWORD error, DWORD bytes, DWORD opcode, PyObject *cont, PyObject *data)
{
    PyObject *result, *value;
    PyObject *func, *args, *kwargs;
    PyObject *ex_type, *ex_val, *ex_tb;
    BOOL success;
    if(opcode == OP_INVOKE)
    {
        func = PyTuple_GetItem(data, 0);
        args = PyTuple_GetItem(data, 1);
        kwargs = PyTuple_GetItem(data, 2);
        value = PyObject_Call(func, args, kwargs);
        if(value)
        {
            success = TRUE;
        }
        else if(!cont)
        {
            // if there is no continuation, propagate the exception to the caller
            return NULL;
        }
        else
        {
            success = FALSE;
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
    }
    else if(opcode == OP_THROW)
    {
        PyErr_SetObject(PyObject_Type(data), data);
        return NULL;
    }
    else if(opcode == OP_READ)
    {
        if(error == ERROR_SUCCESS)
        {
            success = TRUE;
            value = PySequence_GetSlice(data, 0, (Py_ssize_t)bytes);
            if(!value)
                return NULL;
        }
        else if((error == ERROR_BROKEN_PIPE) || (error == ERROR_HANDLE_EOF))
        {
            success = TRUE;
            value = PyString_FromString("");
            if(!value)
                return NULL;
        }
        else
        {
            success = FALSE;
            iocp_win32error(error, "The read operation failed (%s)");
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
    }
    else if(opcode == OP_CONNECT)
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
            else
            {
            */
            success = TRUE;
            Py_INCREF(data);
            value = data;
        }
        else
        {
            success = FALSE;
            iocp_win32error(error, "The connect operation failed (%s)");
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
    }
    else
    {
        if(error == ERROR_SUCCESS)
        {
            success = TRUE;
            Py_INCREF(Py_None);
            value = Py_None;
        }
        else
        {
            success = FALSE;
            iocp_win32error(error, "The operation failed (%s)");
            value = iocp_fetchException();
            if(!value)
                return NULL;
        }
    }

    if(success)
        result = Py_BuildValue("OOO", Py_True, value, cont);
    else
        result = Py_BuildValue("OOO", Py_False, value, cont);
    Py_DECREF(value);
    return result;
}

PyObject * CompletionPort_createFile(CompletionPort *self, PyObject *args)
{
    PyObject *objMode, *fileArgs, *file;
    char *mode, *path;
    DWORD access, creation, flags;
    HANDLE hFile;
    if(!PyArg_ParseTuple(args, "sO", &path, &objMode))
        return NULL;
    if(objMode == Py_None)
    {
        mode = 0;
    }
    else if(PyString_Check(objMode))
    {
        mode = PyString_AsString(objMode);
    }
    else
    {
        PyErr_SetString(PyExc_TypeError, "Mode should be a string or None");
        return NULL;
    }
 
    if(strcmpi("w", mode) == 0)
    {
        access = GENERIC_WRITE;
        creation = CREATE_ALWAYS;
    }
    else if(strcmpi("a", mode) == 0)
    {
        access = FILE_APPEND_DATA;
        creation = OPEN_ALWAYS;
    }
    else if(strcmpi("r+", mode) == 0)
    {
        access = GENERIC_READ | GENERIC_WRITE;
        creation = OPEN_EXISTING;
    }
    else if(strcmpi("w+", mode) == 0)
    {
        access = GENERIC_READ | GENERIC_WRITE;
        creation =  CREATE_ALWAYS;
    }
    else if(strcmpi("a+", mode) == 0)
    {
        access = GENERIC_READ | GENERIC_WRITE;
        creation = OPEN_ALWAYS;
    }
    else
    {
        access = GENERIC_READ;
        creation = OPEN_EXISTING;
    }
    flags = FILE_FLAG_OVERLAPPED | FILE_ATTRIBUTE_NORMAL;
    hFile = CreateFileA(path, access, 0, NULL, creation, flags, NULL);
    if(hFile == INVALID_HANDLE_VALUE)
    {
        iocp_lastwin32error("Could not open or create file (%s)");
        return NULL;
    }
    else if(!CreateIoCompletionPort((HANDLE)hFile, self->hPort, (ULONG_PTR)hFile, 0))
    {
        iocp_lastwin32error("Could not register file (%s)");
        CloseHandle(hFile);
        return NULL;
    }

    return CompletionPort_createAsyncFile(self, hFile);
}

PyObject * CompletionPort_createPipe(CompletionPort *self, PyObject *args)
{
    PyObject *pipe1, *pipe2, *pipes;
    HANDLE hRead, hWrite;
    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    if(!iocp_createAsyncPipe(&hRead, &hWrite))
        return NULL;
    if(!CreateIoCompletionPort((HANDLE)hRead, self->hPort, (ULONG_PTR)hRead, 0))
    {
        iocp_lastwin32error("Could not register read pipe (%s)");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }
    if(!CreateIoCompletionPort((HANDLE)hWrite, self->hPort, (ULONG_PTR)hWrite, 0))
    {
        iocp_lastwin32error("Could not register write pipe (%s)");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }

    pipe1 = CompletionPort_createAsyncFile(self, hRead);
    if(!pipe1)
        return NULL;

    pipe2 = CompletionPort_createAsyncFile(self, hWrite);
    if(!pipe2)
    {
        Py_DECREF(pipe1);
        return NULL;
    }

    pipes = Py_BuildValue("OO", pipe1, pipe2);
    Py_DECREF(pipe1);
    Py_DECREF(pipe2);
    return pipes;
}

PyObject * CompletionPort_createAsyncFile(CompletionPort *self, HANDLE hFile)
{
    PyObject *fileArgs, *file;
    fileArgs = Py_BuildValue("(n)", hFile);
    if(!fileArgs)
        return NULL;
    file = PyObject_CallObject((PyObject *)&AsyncFileType, fileArgs);
    Py_DECREF(fileArgs);
    return file;
}

PyObject * CompletionPort_createSocket(CompletionPort *self, PyObject *args)
{
    int family, type, protocol;
    PyObject *ctorArgs, *sock;
    if(!PyArg_ParseTuple(args, "lll", &family, &type, &protocol))
        return NULL;
    ctorArgs = Py_BuildValue("Olll", self, family, type, protocol);
    sock = PyObject_CallObject((PyObject *)&AsyncSocketType, ctorArgs);
    Py_DECREF(ctorArgs);
    return sock;
}

BOOL CompletionPort_registerFile(CompletionPort *self, HANDLE hFile)
{
    if(!CreateIoCompletionPort((HANDLE)hFile, self->hPort, (ULONG_PTR)hFile, 0))
    {
        iocp_lastwin32error("Could not register file (%s)");
        return FALSE;
    }
    else
    {
        return TRUE;
    }
}