#include <Python.h>
#include <stdio.h>
#include <windows.h>
#include "iocp.h"
#include "completionport.h"
#include "future.h"
#include "AsyncFile.h"

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

PyMODINIT_FUNC init_iocp(void)
{
    PyObject *m, *err;

    if(PyType_Ready(&CompletionPortType) < 0)
        return;

    if(PyType_Ready(&FutureType) < 0)
        return;

    if(PyType_Ready(&AsyncFileType) < 0)
        return;

    m = Py_InitModule3("_iocp", iocp_Methods,
       "Wrapper around Windows' I/O completion port interface");

    Py_INCREF(&CompletionPortType);
    PyModule_AddObject(m, "CompletionPort", (PyObject *)&CompletionPortType);

    Py_INCREF(&AsyncFileType);
    PyModule_AddObject(m, "AsyncFile", (PyObject *)&AsyncFileType);

    Py_INCREF(&FutureType);
    PyModule_AddObject(m, "Future", (PyObject *)&FutureType);

    iocp_addConstant(m, "ERROR_SUCCESS", ERROR_SUCCESS);
    iocp_addConstant(m, "ERROR_HANDLE_EOF", ERROR_HANDLE_EOF);
    iocp_addConstant(m, "ERROR_BROKEN_PIPE", ERROR_BROKEN_PIPE);

    iocp_addConstant(m, "OP_CLOSE", OP_CLOSE);
    iocp_addConstant(m, "OP_INVOKE", OP_INVOKE);
}

void iocp_addConstant(PyObject *module, char *name, DWORD value)
{
    PyObject *obj = PyLong_FromLong(value);
    if(obj)
        PyModule_AddObject(module, name, obj);
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
        iocp_win32error("Could not create a pipe (%s)");
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
        iocp_win32error("Could not create a pipe (%s)");
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

void iocp_win32error(const char *format)
{
    DWORD error = GetLastError();
    PyObject *exc = iocp_createWinError(error, format);
    if(exc)
    {
        PyErr_SetObject(PyObject_Type(exc), exc);
        Py_DECREF(exc);
    }
}

PyObject * iocp_createWinError(DWORD error, const char *format)
{
    PyObject *args, *exc;
    char message[512], text[512];
    char *str;

    ZeroMemory(message, sizeof(message));
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM, 0, error, LANG_NEUTRAL, 
        message, sizeof(message), 0);
    if(format)
    {
        snprintf(text, sizeof(text), format, message);
        str = text;
    }
    else
    {
        str = message;
    }

    args = Py_BuildValue("ls", &error, &str);
    if(!args)
        return NULL;

    exc = PyObject_CallObject(PyExc_WindowsError, args);
    Py_DECREF(args);
    return exc;
}
