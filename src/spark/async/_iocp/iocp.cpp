#include <Python.h>
#include <stdio.h>
#include "iocp.h"

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved)
{
	switch (ul_reason_for_call)
	{
	case DLL_PROCESS_ATTACH:
	case DLL_THREAD_ATTACH:
	case DLL_THREAD_DETACH:
	case DLL_PROCESS_DETACH:
		break;
	}
	return TRUE;
}

static PyMethodDef iocp_Methods[] =
{
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyMethodDef Overlapped_methods[] =
{
    {"address", (PyCFunction)Overlapped_address, METH_NOARGS, "Return the address of the OVERLAPPED structure."},
    {"setOffset", Overlapped_setOffset, METH_VARARGS, "Set the offset inside the OVERLAPPED structure."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyMethodDef CompletionPort_methods[] =
{
    {"close",  CompletionPort_close, METH_VARARGS, "Close the completion port."},
    {"post",  CompletionPort_post, METH_VARARGS, "Directly post the objects to the completion port."},
    {"wait",  CompletionPort_wait, METH_VARARGS, 
    "Wait for an operation to be finished and return a (ID, tag, bytes, objs) tuple containing the result."},
    {"createFile", CompletionPort_createFile, METH_VARARGS, "Create or open a file in asynchronous mode."},
    {"createPipe", CompletionPort_createPipe, METH_VARARGS, "Create an asynchronous pipe."},
    {"closeFile", CompletionPort_closeFile, METH_VARARGS, "Close a file, pipe or socket opened for the completion port."},
    {"beginRead", CompletionPort_beginRead, METH_VARARGS, "Start an asynchronous read operation on a file."},
    {"beginWrite", CompletionPort_beginWrite, METH_VARARGS, "Start an asynchronous write operation on a file."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyTypeObject CompletionPortType =
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

static PyTypeObject OverlappedType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.Overlapped",                                     /*tp_name*/
    sizeof(Overlapped),                                     /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)Overlapped_dealloc,                         /*tp_dealloc*/
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
    "Overlapped objects",                                   /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    Overlapped_methods,                                     /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    (initproc)Overlapped_init,                              /* tp_init */
    0,                                                      /* tp_alloc */
    Overlapped_new,                                         /* tp_new */
};

PyMODINIT_FUNC init_iocp(void)
{
    PyObject *m;

    if(PyType_Ready(&OverlappedType) < 0)
        return;

    if(PyType_Ready(&CompletionPortType) < 0)
        return;

    m = Py_InitModule3("_iocp", iocp_Methods,
       "Wrapper around Windows' I/O completion port interface");

    Py_INCREF(&OverlappedType);
    //PyModule_AddObject(m, "Overlapped", (PyObject *)&OverlappedType);

    Py_INCREF(&CompletionPortType);
    PyModule_AddObject(m, "CompletionPort", (PyObject *)&CompletionPortType);
}

BOOL iocp_createAsyncPipe(PHANDLE hRead, PHANDLE hWrite)
{
    HANDLE readHandle, writeHandle;
    char pipeName[256];
    static int pipeID = 0;

    // generate an unique name for the pipe, using the process ID and a process-wide counter
    snprintf(pipeName, 256, "\\\\.\\Pipe\\iocp.async-pipe.%08x.%08x",
        GetCurrentProcessId(), pipeID++);

    readHandle = CreateNamedPipeA(pipeName,
        PIPE_ACCESS_INBOUND | FILE_FLAG_FIRST_PIPE_INSTANCE | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1, 0, 0, 0, NULL);
    if(readHandle == INVALID_HANDLE_VALUE)
    {
        iocp_win32error(PyExc_Exception, "Could not create a pipe (%s)");
        if(hRead)
            *hRead = INVALID_HANDLE_VALUE;
        if(hWrite)
            *hWrite = INVALID_HANDLE_VALUE;
        return FALSE;
    }

     writeHandle = CreateFileA(pipeName, GENERIC_WRITE, 0, NULL, 
         OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OVERLAPPED, NULL);

    if(writeHandle == INVALID_HANDLE_VALUE)
    {
        iocp_win32error(PyExc_Exception, "Could not create a pipe (%s)");
        CloseHandle(readHandle);
        if(hRead)
            *hRead = INVALID_HANDLE_VALUE;
        if(hWrite)
            *hWrite = INVALID_HANDLE_VALUE;
        return FALSE;
    }

    if(hRead)
        *hRead = readHandle;
    if(hWrite)
        *hWrite = writeHandle;
    return TRUE;
}

void iocp_win32error(PyTypeObject *excType, const char *format)
{
    char message[512], text[512];
    ZeroMemory(message, sizeof(message));
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM, 0, GetLastError(), LANG_NEUTRAL, 
        message, sizeof(message), 0);
    if(format)
    {
        snprintf(text, sizeof(text), format, message);
        PyErr_SetString(excType, text);
    }
    else
    {
        PyErr_SetString(excType, message);
    }
}

void Overlapped_dealloc(Overlapped* self)
{
    self->body.self = NULL;
    printf("Freeing overlapped, data refcount will be: %i\n", self->body.data->ob_refcnt);
    Py_CLEAR(self->body.data);
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * Overlapped_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Overlapped *self = (Overlapped *)type->tp_alloc(type, 0);
    if(self != NULL)
    {
        ZeroMemory(&self->body.ov, sizeof(OVERLAPPED));
        Py_INCREF(Py_None);
        self->body.id = Py_None;
        Py_INCREF(Py_None);
        self->body.self = Py_None;
        Py_INCREF(Py_None);
        self->body.data = Py_None;
    }
    return (PyObject *)self;
}

int Overlapped_init(Overlapped *self, PyObject *args, PyObject *kwds)
{
    PyObject *old;

    if(!PyTuple_Check(args))
        return -1;
    old = self->body.id;
    self->body.id = Py_BuildValue("n", self);
    Py_XDECREF(old);
    old = self->body.self;
    self->body.self = self;
    Py_XDECREF(old);
    old = self->body.data;
    Py_INCREF(args);
    self->body.data = args;
    Py_XDECREF(old);
    return 0;
}

PyObject * Overlapped_address(Overlapped *self)
{
    return Py_BuildValue("n", &self->body.ov);
}

PyObject * Overlapped_setOffset(Overlapped *self, PyObject *args)
{
    ssize_t offset = 0;
    if(!PyArg_ParseTuple(args, "n", &offset))
        return NULL;
    OVERLAPPED_setOffset(&self->body.ov, offset);
    Py_RETURN_NONE;
}

void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset)
{
    ov->Offset = (size_t)offset & 0x00000000ffffffff;
    ov->OffsetHigh = (size_t)offset & 0xffffffff00000000;
}

Overlapped * Overlapped_create(PyObject *args)
{
    Overlapped *over, *ovkw;
    int ret;

    ovkw = Py_BuildValue("{}");
    if(!ovkw)
    {
        return NULL;
    }

    over = Overlapped_new(&OverlappedType, args, ovkw);
    if(!over)
    {
        Py_DECREF(ovkw);
        return NULL;
    }

    ret = Overlapped_init(over, args, ovkw);
    Py_DECREF(ovkw);
    if(ret != 0)
    {
        Py_DECREF(over);
        return NULL;
    }
    return over;
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
        iocp_win32error(PyExc_Exception, "Could not create completion port (%s)");
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
    Overlapped *ov;
    if(!PyTuple_Check(args))
        return NULL;
    ov = Overlapped_create(args);
    if(!ov)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the overlapped object");
        return NULL;
    }
    // don't decrement ov's refcount, so it stays alive until wait() returns
    PostQueuedCompletionStatus(self->hPort, 0, 
        (ULONG_PTR)INVALID_HANDLE_VALUE, (LPOVERLAPPED)&ov->body);
    Py_INCREF(ov->body.id);
    return ov->body.id;
}

PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args)
{
    BOOL success;
    DWORD bytes = 0;
    ULONG_PTR tag = 0;
    iocp_OVERLAPPED *lpOver = NULL;
    Overlapped *ov = NULL;
    PyObject *id = NULL;
    PyObject *data = NULL;

    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
    success = GetQueuedCompletionStatus(self->hPort, &bytes, &tag, (LPOVERLAPPED *)&lpOver, -1);
    Py_END_ALLOW_THREADS
    if(!success)
    {
        iocp_win32error(PyExc_Exception, 
            "Waiting for an operation's completion failed (%s)");
        return NULL;
    }

    ov = (Overlapped *)lpOver->self;
    Py_INCREF(ov->body.id);
    id = ov->body.id;
    Py_INCREF(ov->body.data);
    data = ov->body.data;
    Py_DECREF(ov);
    return Py_BuildValue("(OnlO)", id, tag, bytes, data); 
}

PyObject * CompletionPort_createFile(CompletionPort *self, PyObject *args)
{
    PyObject *objMode;
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
        iocp_win32error(PyExc_Exception, "Could not open or create file (%s)");
        return NULL;
    }
    else if(!CreateIoCompletionPort((HANDLE)hFile, self->hPort, (ULONG_PTR)hFile, 0))
    {
        iocp_win32error(PyExc_Exception, "Could not register file (%s)");
        CloseHandle(hFile);
        return NULL;
    }
    return Py_BuildValue("n", hFile);
}

PyObject * CompletionPort_createPipe(CompletionPort *self, PyObject *args)
{
    HANDLE hRead, hWrite;
    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    if(!iocp_createAsyncPipe(&hRead, &hWrite))
        return NULL;
    if(!CreateIoCompletionPort((HANDLE)hRead, self->hPort, (ULONG_PTR)hRead, 0))
    {
        iocp_win32error(PyExc_Exception, "Could not register read pipe (%s)");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }
    if(!CreateIoCompletionPort((HANDLE)hWrite, self->hPort, (ULONG_PTR)hWrite, 0))
    {
        iocp_win32error(PyExc_Exception, "Could not register write pipe (%s)");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return NULL;
    }
    return Py_BuildValue("nn", hRead, hWrite);
}

PyObject * CompletionPort_closeFile(CompletionPort *self, PyObject *args)
{
    HANDLE hFile;
    if(!PyArg_ParseTuple(args, "n", &hFile))
        return NULL;
    if(!CloseHandle(hFile))
    {
        iocp_win32error(PyExc_Exception, "Could not close file handle (%s)");
        return NULL;
    }
    Py_RETURN_NONE;
}

PyObject * CompletionPort_beginRead(CompletionPort *self, PyObject *args)
{
    PyObject *cont, *data, *buffer;
    Overlapped *over;
    DWORD opcode, size, error;
    Py_ssize_t hFile, position, bufferSize;
    void *pBuffer = 0;

    if(!PyArg_ParseTuple(args, "lnlnO", &opcode, &hFile, &size, &position, &cont))
        return NULL;

    buffer = PyBuffer_New(size);
    if(!buffer)
    {
        return NULL;
    }
    
    bufferSize = buffer->ob_type->tp_as_buffer->bf_getwritebuffer(buffer, 0, &pBuffer);
    if(((ssize_t)size > bufferSize) || !pBuffer)
    {
        PyErr_SetString(PyExc_Exception, "Couldn't allocate the buffer");
        Py_DECREF(buffer);
        return NULL;
    }

    Py_INCREF(cont);
    data = Py_BuildValue("(lOO)", opcode, buffer, cont);
    if(!data)
    {
        Py_DECREF(cont);
        Py_DECREF(buffer);
        return NULL;
    }
    over = Overlapped_create(data);
    Py_DECREF(data);
    OVERLAPPED_setOffset(&over->body.ov, position);
    if(!ReadFile((HANDLE)hFile, pBuffer, size, NULL, (LPOVERLAPPED)&over->body))
    {
        error = GetLastError();
        if(error != ERROR_IO_PENDING)
        {
            Py_DECREF(over);
            iocp_win32error(PyExc_Exception, "Reading the file failed (%s)");
            return NULL;
        }
    }
    // don't decrement over's refcount, so it stays alive until wait() returns
    Py_RETURN_NONE;
}

PyObject * CompletionPort_beginWrite(CompletionPort *self, PyObject *args)
{
    PyObject *cont, *data, *buffer;
    Overlapped *over;
    DWORD opcode, error;
    Py_ssize_t hFile, position, bufferSize;
    void *pBuffer = 0;

    if(!PyArg_ParseTuple(args, "lnOnO", &opcode, &hFile, &buffer, &position, &cont))
        return NULL;
    else if((PyObject_AsReadBuffer(buffer, &pBuffer, &bufferSize) != 0) || (bufferSize <= 0))
    {
        PyErr_SetString(PyExc_Exception, "Couldn't access the buffer for reading");
        return NULL;
    }

    Py_INCREF(cont);
    Py_INCREF(buffer);
    data = Py_BuildValue("(lOO)", opcode, buffer, cont);
    if(!data)
    {
        Py_DECREF(cont);
        Py_DECREF(buffer);
        return NULL;
    }
    over = Overlapped_create(data);
    Py_DECREF(data);
    OVERLAPPED_setOffset(&over->body.ov, position);
    if(!WriteFile((HANDLE)hFile, pBuffer, (DWORD)bufferSize, NULL, (LPOVERLAPPED)&over->body))
    {
        error = GetLastError();
        if(error != ERROR_IO_PENDING)
        {
            Py_DECREF(over);
            iocp_win32error(PyExc_Exception, "Writing the file failed (%s)");
            return NULL;
        }
    }
    // don't decrement over's refcount, so it stays alive until wait() returns
    Py_RETURN_NONE;
}