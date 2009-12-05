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

PyMODINIT_FUNC init_iocp(void)
{
    PyObject *m, *err;

    if(PyType_Ready(&CompletionPortType) < 0)
        return;

    m = Py_InitModule3("_iocp", iocp_Methods,
       "Wrapper around Windows' I/O completion port interface");

    Py_INCREF(&CompletionPortType);
    PyModule_AddObject(m, "CompletionPort", (PyObject *)&CompletionPortType);

    err = PyLong_FromLong(ERROR_SUCCESS);
    if(err)
        PyModule_AddObject(m, "ERROR_SUCCESS", err);

    err = PyLong_FromLong(ERROR_HANDLE_EOF);
    if(err)
        PyModule_AddObject(m, "ERROR_HANDLE_EOF", err);

    err = PyLong_FromLong(ERROR_BROKEN_PIPE);
    if(err)
        PyModule_AddObject(m, "ERROR_BROKEN_PIPE", err);
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

void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset)
{
    ov->Offset = (DWORD)((size_t)offset & 0x00000000ffffffff);
    ov->OffsetHigh = (DWORD)(((size_t)offset & 0xffffffff00000000) >> 32);
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
    IOCPOverlapped *ov;
    if(!PyTuple_Check(args))
        return NULL;
    ov = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&ov->ov, sizeof(OVERLAPPED));
    Py_INCREF(args);
    ov->data = args;
    if(!ov)
    {
        PyErr_SetString(PyExc_Exception, "Could not create the overlapped object");
        return NULL;
    }
    // don't decrement ov's refcount, so it stays alive until wait() returns
    PostQueuedCompletionStatus(self->hPort, 0, 
        (ULONG_PTR)INVALID_HANDLE_VALUE, (LPOVERLAPPED)ov);
    Py_RETURN_NONE;
}

PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args)
{
    BOOL success = FALSE;
    DWORD bytes = 0, error = ERROR_SUCCESS;
    ULONG_PTR tag = 0;
    IOCPOverlapped *ov = NULL;
    PyObject *result = NULL;

    if(!PyArg_ParseTuple(args, ""))
        return NULL;
    Py_BEGIN_ALLOW_THREADS
    success = GetQueuedCompletionStatus(self->hPort, &bytes, &tag, (LPOVERLAPPED *)&ov, -1);
    Py_END_ALLOW_THREADS
    if(!success)
    {
        if(ov == NULL)
        {
            // Waiting for the completion of an operation failed
            iocp_win32error(PyExc_Exception, 
                "Waiting for an operation's completion failed (%s)");
            return NULL;
        }
        else
        {
            // The I/O operation itself failed
            error = GetLastError();
        }
    }

    result = Py_BuildValue("(nllO)", tag, error, bytes, ov->data);
    Py_DECREF(ov->data); // INCREF was done in beginRead/beginWrite/post to keep it alive
    free(ov);
    return result;
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
    IOCPOverlapped *over;
    DWORD opcode, size, error = ERROR_SUCCESS;
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

    data = Py_BuildValue("(lOO)", opcode, buffer, cont);
    Py_DECREF(buffer);
    if(!data)
    {
        return NULL;
    }

    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->data = data;
    OVERLAPPED_setOffset(&over->ov, position);
    if(!ReadFile((HANDLE)hFile, pBuffer, size, NULL, (LPOVERLAPPED)over))
    {
        error = GetLastError();
        if(error == ERROR_IO_PENDING)
        {
            // don't decrement data's refcount, so it stays alive until wait() returns
            error = ERROR_SUCCESS;
        }
        else
        {
            Py_DECREF(over->data);
            free(over);
        }
    }
    return PyLong_FromLong(error);
}

PyObject * CompletionPort_beginWrite(CompletionPort *self, PyObject *args)
{
    PyObject *cont, *data, *buffer;
    IOCPOverlapped *over;
    DWORD opcode, error = ERROR_SUCCESS;
    Py_ssize_t hFile, position, bufferSize;
    void *pBuffer = 0;

    if(!PyArg_ParseTuple(args, "lnOnO", &opcode, &hFile, &buffer, &position, &cont))
        return NULL;
    else if((PyObject_AsReadBuffer(buffer, &pBuffer, &bufferSize) != 0) || (bufferSize <= 0))
    {
        PyErr_SetString(PyExc_Exception, "Couldn't access the buffer for reading");
        return NULL;
    }

    data = Py_BuildValue("(lOO)", opcode, buffer, cont);
    if(!data)
    {    
        return NULL;
    }
    over = (IOCPOverlapped *)malloc(sizeof(IOCPOverlapped));
    ZeroMemory(&over->ov, sizeof(OVERLAPPED));
    over->data = data;
    OVERLAPPED_setOffset(&over->ov, position);
    if(!WriteFile((HANDLE)hFile, pBuffer, (DWORD)bufferSize, NULL, (LPOVERLAPPED)over))
    {
        error = GetLastError();
        if(error == ERROR_IO_PENDING)
        {
            // don't decrement data's refcount, so it stays alive until wait() returns
            error = ERROR_SUCCESS;
        }
        else
        {
            Py_DECREF(over->data);
            free(over);
        }
    }
    return PyLong_FromLong(error);
}
