#ifndef PYTHON_IOCP
#define PYTHON_IOCP

#include <windows.h>
#include <stdio.h>

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_win32error(PyTypeObject *excType, const char *format);
PyObject *iocp_beginRead(PyObject *self, PyObject *args);

typedef struct
{
    PyObject_HEAD
    HANDLE hPort;
} CompletionPort;

typedef struct
{
    OVERLAPPED ov;
    PyObject *id;
    PyObject *self;
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
PyObject * CompletionPort_register(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_memorize(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_post(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args);

#endif