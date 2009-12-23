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
#include <windows.h>
#include "AsyncFile.h"
#include "completionport.h"
#include "future.h"
#include "iocp.h"

static PyMethodDef AsyncFile_methods[] =
{
    {"beginRead", (PyCFunction)AsyncFile_beginRead, METH_VARARGS, "Start an asynchronous read operation."},
    {"beginWrite", (PyCFunction)AsyncFile_beginWrite, METH_VARARGS, "Start an asynchronous write operation."},
    {"read", (PyCFunction)AsyncFile_read, METH_VARARGS, "Start a synchronous read operation."},
    {"write", (PyCFunction)AsyncFile_write, METH_VARARGS, "Start a synchronous write operation."},
    {"fileno", (PyCFunction)AsyncFile_fileno, METH_VARARGS, "Return the file's handle."},
    {"close", (PyCFunction)AsyncFile_close, METH_NOARGS, "Close the file."},
    {"__enter__", (PyCFunction)AsyncFile_enter, METH_VARARGS, ""},
    {"__exit__", (PyCFunction)AsyncFile_exit, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyTypeObject AsyncFileType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.AsyncFile",                                      /*tp_name*/
    sizeof(AsyncFile),                                      /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)AsyncFile_dealloc,                          /*tp_dealloc*/
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
    "AsyncFile objects",                                    /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    AsyncFile_methods,                                      /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    0,                                                      /* tp_init */
    0,                                                      /* tp_alloc */
    AsyncFile_new,                                          /* tp_new */
};

void AsyncFile_dealloc(AsyncFile *self)
{
    AsyncFile_close(self);
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * AsyncFile_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    AsyncFile *self;
    PyObject *port;
    HANDLE hFile;

    if(!PyArg_ParseTuple(args, "On", &port, &hFile))
    {
        return NULL;
    }
    else if(!PyObject_TypeCheck(port, &CompletionPortType))
    {
        PyErr_SetString(PyExc_TypeError, "The first argument should be a CompletionPort instance");
        return NULL;
    }

    self = (AsyncFile *)type->tp_alloc(type, 0);
    if(self != NULL)
    {
        Py_INCREF(port);
        self->port = (CompletionPort *)port;
        self->hFile = hFile;
    }
    return (PyObject *)self;
}

PyObject * AsyncFile_beginRead(AsyncFile *self, PyObject *args)
{
    Py_ssize_t size, position = 0;
    PyObject *cont, *arg, *ret;
    DWORD error;

    if(!PyArg_ParseTuple(args, "n|n", &size, &position))
        return NULL;

    cont = PyObject_CallObject((PyObject *)&FutureType, NULL);
    if(!cont)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the continuation");
        return NULL;
    }

    if(!AsyncFile_readFile(self->hFile, size, position, cont, &error))
    {
        Py_DECREF(cont);
        return NULL;
    }
    else if((error == ERROR_BROKEN_PIPE) || (error == ERROR_HANDLE_EOF))
    {
        arg = PyString_FromString("");
        ret = CompletionPort_post(self->port, OP_READ, cont, arg);
        Py_DECREF(arg);
        if(!ret)
        {
            Py_DECREF(cont);
            return NULL;
        }
    }
    else if(error != ERROR_SUCCESS)
    {
        iocp_win32error(error, NULL);
        Py_DECREF(cont);
        return NULL;
    }
    return cont;
}

BOOL AsyncFile_readFile(HANDLE hFile, Py_ssize_t size, Py_ssize_t position, PyObject *cont, DWORD *pError)
{
    PyObject *buffer;
    IOCPOverlapped *over;
    DWORD error = ERROR_SUCCESS;
    void *pBuffer = 0;

    buffer = iocp_allocBuffer(size, &pBuffer);
    if(!buffer)
        return FALSE;
    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->opcode = OP_READ;
    Py_INCREF(cont);
    over->cont = cont;
    over->data = buffer;
    OVERLAPPED_setOffset(&over->ov, position);
    if(!ReadFile(hFile, pBuffer, (DWORD)size, NULL, (LPOVERLAPPED)over))
    {
        error = GetLastError();
        if(error == ERROR_IO_PENDING)
        {
            // don't decrement cont and data's refcount, so they remain alive until wait() returns
            error = ERROR_SUCCESS;
        }
        else
        {
            Py_DECREF(over->data);
            free(over);
        }
    }
    if(pError)
        *pError = error;
    return TRUE;
}

PyObject * AsyncFile_read(AsyncFile *self, PyObject *args)
{
    PyObject *cont, *ret;
    cont = AsyncFile_beginRead(self, args);
    if(!cont)
        return NULL;
    ret = PyObject_CallMethod(cont, "wait", "");
    Py_DECREF(cont);
    return ret;
}

PyObject * AsyncFile_beginWrite(AsyncFile *self, PyObject *args)
{
    Py_ssize_t position = 0;
    PyObject *buffer, *cont;
    DWORD error;

    if(!PyArg_ParseTuple(args, "O|n", &buffer, &position))
        return NULL;

    cont = PyObject_CallObject((PyObject *)&FutureType, NULL);
    if(!cont)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the continuation");
        return NULL;
    }

    if(!AsyncFile_writeFile(self->hFile, buffer, position, cont, &error))
    {
        Py_DECREF(cont);
        return NULL;
    }
    else if(error != ERROR_SUCCESS)
    {
        iocp_win32error(error, NULL);
        Py_DECREF(cont);
        return NULL;
    }
    return cont;
}

BOOL AsyncFile_writeFile(HANDLE hFile, PyObject *buffer, Py_ssize_t position, PyObject *cont, DWORD *pError)
{
    IOCPOverlapped *over;
    DWORD error = ERROR_SUCCESS;
    Py_ssize_t bufferSize;
    const void *pBuffer = 0;

    if((PyObject_AsReadBuffer(buffer, &pBuffer, &bufferSize) != 0) || (bufferSize <= 0))
    {
        PyErr_SetString(PyExc_Exception, "Couldn't access the buffer for reading");
        return FALSE;
    }

    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->opcode = OP_WRITE;
    Py_INCREF(cont);
    over->cont = cont;
    Py_INCREF(buffer);
    over->data = buffer;
    OVERLAPPED_setOffset(&over->ov, position);
    if(!WriteFile(hFile, pBuffer, (DWORD)bufferSize, NULL, (LPOVERLAPPED)over))
    {
        error = GetLastError();
        if(error == ERROR_IO_PENDING)
        {
            // don't decrement cont and data's refcount, so they remain alive until wait() returns
            error = ERROR_SUCCESS;
        }
        else
        {
            Py_DECREF(over->data);
            free(over);
        }
    }
    if(pError)
        *pError = error;
    return TRUE;
}

PyObject * AsyncFile_write(AsyncFile *self, PyObject *args)
{
    PyObject *cont, *ret;
    cont = AsyncFile_beginWrite(self, args);
    if(!cont)
        return NULL;
    ret = PyObject_CallMethod(cont, "wait", "");
    Py_DECREF(cont);
    return ret;
}

PyObject * AsyncFile_fileno(AsyncFile *self, PyObject *args)
{
    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    return PyInt_FromSize_t((size_t)self->hFile);
}

PyObject * AsyncFile_close(AsyncFile *self)
{
    if(self->hFile)
    {
        CloseHandle(self->hFile);
        self->hFile = NULL;
    }
    Py_RETURN_NONE;
}

PyObject * AsyncFile_enter(AsyncFile *self, PyObject *args)
{
    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    Py_INCREF(self);
    return (PyObject *)self;
}

PyObject * AsyncFile_exit(AsyncFile *self, PyObject *args)
{
    PyObject *type, *val, *tb, *ret;
    if(!PyArg_ParseTuple(args, "OOO", &type, &val, &tb))
        return NULL;
    
    ret = AsyncFile_close(self);
    if(!ret)
        return NULL;
    Py_DECREF(ret);
    Py_RETURN_NONE;
}

PyObject * iocp_getResult_read(DWORD error, DWORD bytes, PyObject *data, BOOL *success)
{
    if(error == ERROR_SUCCESS)
    {
        *success = TRUE;
        return PySequence_GetSlice(data, 0, (Py_ssize_t)bytes);
    }
    else if((error == ERROR_BROKEN_PIPE) || (error == ERROR_HANDLE_EOF) || (error == ERROR_OPERATION_ABORTED))
    {
        *success = TRUE;
        return PyString_FromString("");
    }
    else
    {
        *success = FALSE;
        iocp_win32error(error, "The read operation failed (%s)");
        return iocp_fetchException();
    }
}

PyObject * iocp_getResult_write(DWORD error, DWORD bytes, PyObject *data, BOOL *success)
{
    if(error == ERROR_SUCCESS)
    {
        *success = TRUE;
        Py_RETURN_NONE;
    }
    else
    {
        *success = FALSE;
        iocp_win32error(error, "The operation failed (%s)");
        return iocp_fetchException();
    }
}
