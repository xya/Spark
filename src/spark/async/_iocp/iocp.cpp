#include <Python.h>
#include <stdio.h>
#include <windows.h>
#include "iocp.h"
#include "completionport.h"
#include "future.h"

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

    m = Py_InitModule3("_iocp", iocp_Methods,
       "Wrapper around Windows' I/O completion port interface");

    Py_INCREF(&CompletionPortType);
    PyModule_AddObject(m, "CompletionPort", (PyObject *)&CompletionPortType);

    Py_INCREF(&FutureType);
    PyModule_AddObject(m, "Future", (PyObject *)&FutureType);

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
    char message[512], text[512];
    ZeroMemory(message, sizeof(message));
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM, 0, GetLastError(), LANG_NEUTRAL, 
        message, sizeof(message), 0);
    if(format)
    {
        snprintf(text, sizeof(text), format, message);
        PyErr_SetString(PyExc_WindowsError, text);
    }
    else
    {
        PyErr_SetString(PyExc_WindowsError, message);
    }
}
