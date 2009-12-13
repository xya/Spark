#ifndef PYTHON_IOCP_FUTURE
#define PYTHON_IOCP_FUTURE

extern PyTypeObject FutureType;

typedef struct
{
    PyObject_HEAD
    int state;
    PyObject *result;
    PyObject *callback;
    PyObject *args;
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
void Future_get_result(Future *self, int *pState, PyObject **pResult, HANDLE *pEvent);
BOOL Future_set_result(Future *self, int state, PyObject *result);
PyObject * Future_completed(Future *self, PyObject *args);
PyObject * Future_failed(Future *self, PyObject *args);
PyObject * Future_after(Future *self, PyObject *args);
BOOL Future_callback_args(Future *self, PyObject *args, PyObject **cb, PyObject **cbargs);
PyObject * Future_pending_getter(Future *self, void *closure);
PyObject * Future_result_getter(Future *self, void *closure);

#endif