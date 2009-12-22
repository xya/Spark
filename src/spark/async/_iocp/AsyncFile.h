#ifndef PYTHON_IOCP_ASYNC_FILE
#define PYTHON_IOCP_ASYNC_FILE

extern PyTypeObject AsyncFileType;

typedef struct
{
    PyObject_HEAD
    HANDLE hFile;
} AsyncFile;

void AsyncFile_dealloc(AsyncFile *self);
PyObject * AsyncFile_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
PyObject * AsyncFile_beginRead(AsyncFile *self, PyObject *args);
PyObject * AsyncFile_beginWrite(AsyncFile *self, PyObject *args);
PyObject * AsyncFile_read(AsyncFile *self, PyObject *args);
PyObject * AsyncFile_write(AsyncFile *self, PyObject *args);
PyObject * AsyncFile_close(AsyncFile *self);
PyObject * AsyncFile_enter(AsyncFile *self, PyObject *args);
PyObject * AsyncFile_exit(AsyncFile *self, PyObject *args);

#endif