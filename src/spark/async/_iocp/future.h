#ifndef PYTHON_IOCP_FUTURE
#define PYTHON_IOCP_FUTURE

extern PyTypeObject FutureType;

typedef struct
{
    PyObject_HEAD
    int state;
    PyObject *result;
    CRITICAL_SECTION lock;
    HANDLE hEvent;
} Future;

#define FUTURE_PENDING          0
#define FUTURE_COMPLETED        1
#define FUTURE_FAILED           2

void Future_dealloc(Future* self);
PyObject * Future_new(PyTypeObject *type, PyObject *args, PyObject *kwds);
int Future_init(Future *self, PyObject *args, PyObject *kwds);
PyObject * Future_wait(Future *self, PyObject *args);
void Future_get_result(Future *self, int *pState, PyObject **pResult);
BOOL Future_set_result(Future *self, int state, PyObject *result);
PyObject * Future_completed(Future *self, PyObject *args);
PyObject * Future_after(Future *self, PyObject *args);

#endif