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
    PyObject *id;
    PyObject *self; // not ref-counted to avoid cycles
    PyObject *data;
} iocp_OVERLAPPED;

typedef struct
{
    PyObject_HEAD
    iocp_OVERLAPPED body;
} Overlapped;

void Overlapped_dealloc(Overlapped* self);
PyObject * Overlapped_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int Overlapped_init(Overlapped *self, PyObject *args, PyObject *kwds);
PyObject * Overlapped_address(Overlapped *self);
PyObject * Overlapped_setOffset(Overlapped *self, PyObject *args);
void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset);
Overlapped * Overlapped_create(PyObject *args);

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