#ifndef PYTHON_IOCP
#define PYTHON_IOCP

#include <windows.h>
#include <stdio.h>

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_win32error(PyTypeObject *excType, const char *format);
BOOL iocp_createAsyncPipe(PHANDLE hRead, PHANDLE hWrite);

typedef struct
{
    PyObject_HEAD
    HANDLE hPort;
} CompletionPort;

typedef struct
{
    OVERLAPPED ov;
    PyObject *data;
} IOCPOverlapped;

void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset);

void CompletionPort_dealloc(CompletionPort* self);
PyObject * CompletionPort_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int CompletionPort_init(CompletionPort *self, PyObject *args, PyObject *kwds);
PyObject * CompletionPort_close(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_post(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createFile(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createPipe(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_closeFile(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_beginRead(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_beginWrite(CompletionPort *self, PyObject *args);

#endif