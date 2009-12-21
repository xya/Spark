#ifndef PYTHON_IOCP_COMPLETION_PORT
#define PYTHON_IOCP_COMPLETION_PORT

extern PyTypeObject CompletionPortType;

typedef struct
{
    PyObject_HEAD
    HANDLE hPort;
} CompletionPort;

typedef struct
{
    OVERLAPPED ov;
    DWORD opcode;
    PyObject *cont;
    PyObject *data;
} IOCPOverlapped;

void OVERLAPPED_setOffset(OVERLAPPED *ov, ssize_t offset);

void CompletionPort_dealloc(CompletionPort* self);
PyObject * CompletionPort_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int CompletionPort_init(CompletionPort *self, PyObject *args, PyObject *kwds);
PyObject * CompletionPort_close(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_post(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_complete(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createFile(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createPipe(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createAsyncFile(CompletionPort *self, HANDLE hFile);

#endif