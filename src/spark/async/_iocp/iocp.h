#ifndef PYTHON_IOCP
#define PYTHON_IOCP

#include <windows.h>
#include <stdio.h>

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_win32error(PyTypeObject *excType, const char *format);

typedef struct
{
    PyObject_HEAD
    HANDLE hPort;
} CompletionPort;

typedef struct
{
    PyObject_HEAD
    OVERLAPPED ov;
    PyObject *self;
    PyObject *data;
} Overlapped;

void Overlapped_dealloc(Overlapped* self);
PyObject * Overlapped_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int Overlapped_init(Overlapped *self, PyObject *args, PyObject *kwds);
PyObject * Overlapped_address(Overlapped *self);

void CompletionPort_dealloc(CompletionPort* self);
PyObject * CompletionPort_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int CompletionPort_init(CompletionPort *self, PyObject *args, PyObject *kwds);
PyObject * CompletionPort_close(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_register(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_overlapped(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_freeOverlapped(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_post(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args);

#endif