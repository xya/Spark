#include <Python.h>
#include <windows.h>
#include "completionport.h"
#include "AsyncFile.h"
#include "iocp.h"

static PyMethodDef CompletionPort_methods[] =
{
    {"close", (PyCFunction)CompletionPort_close, METH_VARARGS, "Close the completion port."},
    {"post",  (PyCFunction)CompletionPort_post, METH_VARARGS, "Directly post the objects to the completion port."},
    {"wait",  (PyCFunction)CompletionPort_wait, METH_VARARGS, 
    "Wait for an operation to be finished and return a (ID, tag, bytes, objs) tuple containing the result."},
    {"complete",  (PyCFunction)CompletionPort_complete, METH_VARARGS, 
    "Finish an operation by invoking the callback or continuation with the result."},
    {"createFile", (PyCFunction)CompletionPort_createFile, METH_VARARGS, "Create or open a file in asynchronous mode."},
    {"createPipe", (PyCFunction)CompletionPort_createPipe, METH_VARARGS, "Create an asynchronous pipe."},
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
        iocp_win32error("Could not create completion port (%s)");
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

PyObject * CompletionPort_post(CompletionPort *self, PyObject *args)
{
    DWORD opcode = 0;
    PyObject *cont = Py_None, *data = Py_None;
    IOCPOverlapped *over;

    if(!PyArg_ParseTuple(args, "|lOO", &opcode, &cont, &data))
        return NULL;
    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
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
            iocp_win32error("Waiting for an operation's completion failed (%s)");
            return NULL;
        }
        else
        {
            // The I/O operation itself failed
            error = GetLastError();
        }
    }

    result = Py_BuildValue("(nlllOO)", tag, error, bytes, over->opcode, over->cont, over->data);
    // INCREF was done in beginRead/beginWrite/post to keep these alive
    Py_DECREF(over->cont);
    Py_DECREF(over->data);
    free(over);
    return result;
}

PyObject * CompletionPort_complete(CompletionPort *self, PyObject *args)
{
    DWORD bytes, error, opcode;
    ULONG_PTR tag;
    PyObject *cont, *data, *result, *exc, *ret;
    if(!PyArg_ParseTuple(args, "nlllOO", &tag, &error, &bytes, &opcode, &cont, &data))
        return NULL;

    if(opcode == OP_READ)
    {
        if(error == ERROR_SUCCESS)
        {
            result = PySequence_GetSlice(data, 0, (Py_ssize_t)bytes);
        }
        else if((error == ERROR_BROKEN_PIPE) || (error == ERROR_HANDLE_EOF))
        {
            result = PyString_FromString("");
        }
        else
        {
            exc = iocp_createWinError(error, "The read operation failed (%s)");
            result = NULL;
        }
    }
    else if(opcode == OP_WRITE)
    {
        if(error == ERROR_SUCCESS)
        {
            Py_INCREF(Py_None);
            result = Py_None;
        }
        else
        {
            exc = iocp_createWinError(error, "The write operation failed (%s)");
            result = NULL;
        }
    }

    if(result == NULL)
    {
        if(exc == NULL)
        {
            PyErr_SetString(PyExc_Exception, "Could not create WinError exception");
            return NULL;
        }
        else
        {
            ret = PyObject_CallMethod(cont, "failed", "O", exc);
            Py_DECREF(exc);
            return ret;
        }
    }
    else
    {
        ret = PyObject_CallMethod(cont, "completed", "O", result);
        Py_DECREF(result);
        return ret;
    }
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
        iocp_win32error("Could not open or create file (%s)");
        return NULL;
    }
    else if(!CreateIoCompletionPort((HANDLE)hFile, self->hPort, (ULONG_PTR)hFile, 0))
    {
        iocp_win32error("Could not register file (%s)");
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
        iocp_win32error("Could not register read pipe (%s)");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }
    if(!CreateIoCompletionPort((HANDLE)hWrite, self->hPort, (ULONG_PTR)hWrite, 0))
    {
        iocp_win32error("Could not register write pipe (%s)");
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
    fileArgs = Py_BuildValue("On", self, hFile);
    if(!fileArgs)
        return NULL;
    file = PyObject_CallObject((PyObject *)&AsyncFileType, fileArgs);
    Py_DECREF(fileArgs);
    return file;
}
