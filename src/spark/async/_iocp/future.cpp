#include <Python.h>
#include <windows.h>
#include "future.h"
#include "iocp.h"

static PyMethodDef Future_methods[] =
{
    {"wait", Future_wait, METH_VARARGS, "Wait for the result of the operation to be available."},
    {"after", Future_after, METH_VARARGS, "Register a callable to be invoked after the operation is finished."},
    {"completed", Future_completed, METH_VARARGS, "Indicate the operation is finished."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyGetSetDef Future_getseters[] = 
{
    {"pending", (getter)Future_pending_getter, NULL, "Indicate whether the task is still active or if it is complete.", NULL},
    {"result", (getter)Future_result_getter, NULL, "Access the result of the task. If no result is available yet, \
block until there is. May raise an exception if the task failed or was canceled.", NULL},
    {NULL}  /* Sentinel */
};

PyTypeObject FutureType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.Future",                                         /*tp_name*/
    sizeof(Future),                                         /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)Future_dealloc,                             /*tp_dealloc*/
    0,                                                      /*tp_print*/
    0,                                                      /*tp_getattr*/
    0,                                                      /*tp_setattr*/
    0,                                                      /*tp_compare*/
    0,                                                      /*tp_repr*/
    0,                                                      /*tp_as_number*/
    0,                                                      /*tp_as_sequence*/
    0,                                                      /*tp_as_mapping*/
    0,                                                      /*tp_hash */
    0,                                                      /*tp_call*/
    0,                                                      /*tp_str*/
    0,                                                      /*tp_getattro*/
    0,                                                      /*tp_setattro*/
    0,                                                      /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,                                     /*tp_flags*/
    "Future objects",                                       /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    Future_methods,                                         /* tp_methods */
    0,                                                      /* tp_members */
    Future_getseters,                                       /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    (initproc)Future_init,                                  /* tp_init */
    0,                                                      /* tp_alloc */
    Future_new,                                             /* tp_new */
};

void Future_dealloc(Future* self)
{
    Py_CLEAR(self->result);
    DeleteCriticalSection(&self->lock);
    if(self->hEvent)
    {
        CloseHandle(self->hEvent);
        self->hEvent = NULL;
    }
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * Future_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Future *self = (Future *)type->tp_alloc(type, 0);
    if(self != NULL)
    {
        self->state = 0;
        self->result = NULL;
        InitializeCriticalSection(&self->lock);
        self->hEvent = NULL;
    }
    return (PyObject *)self;
}

int Future_init(Future *self, PyObject *args, PyObject *kwds)
{
    if(!PyArg_ParseTuple(args, ""))
        return -1;
    self->state = FUTURE_PENDING;
    Py_INCREF(Py_None);
    self->result = Py_None;
    return 0;
}

PyObject * Future_wait(Future *self, PyObject *args)
{
    double timeoutSec = -1.0;
    DWORD timeoutMsec;
    DWORD waitResult;
    int state;
    PyObject *result;
    HANDLE hEvent;

    if(!PyArg_ParseTuple(args, "|d", &timeoutSec))
        return NULL;

    if(timeoutSec < 0.0)
        timeoutMsec = INFINITE;
    else
        timeoutMsec = (DWORD)(timeoutSec * 1000.0);
    Future_get_result(self, &state, &result, &hEvent);
    if(state == FUTURE_PENDING)
    {
        // the operation is not finished yet, we have to wait until it is
        Py_BEGIN_ALLOW_THREADS
        waitResult = WaitForSingleObject(hEvent, timeoutMsec);
        Py_END_ALLOW_THREADS
        if(waitResult == WAIT_FAILED)
        {
            iocp_win32error("Waiting for the result of the operation failed (%s)");
            return NULL;
        }
        Future_get_result(self, &state, &result, NULL);
    }
    
    // return the result or propagate the exception the operation raised
    if(state == FUTURE_COMPLETED)
    {
        Py_INCREF(result);
        return result;
    }
    else if(state == FUTURE_FAILED)
    {
        Py_INCREF(result);
        PyErr_SetObject(PyObject_Type(result), result);
        return NULL;
    }
    else
    {
        PyErr_SetString(PyExc_Exception, "The operation didn't complete within the specified duration");
        return NULL;
    }
}

void Future_get_result(Future *self, int *pState, PyObject **pResult, HANDLE *pEvent)
{
    int state;
    PyObject *result;
    HANDLE hEvent;
    EnterCriticalSection(&self->lock);
    state = self->state;
    result = self->result;
    // create an event to wait for the result if we haven't created one yet
    if((state == FUTURE_PENDING) && !self->hEvent && pEvent)
        self->hEvent = CreateEvent(NULL, TRUE, FALSE, NULL);
    hEvent = self->hEvent;
    LeaveCriticalSection(&self->lock);
    if(pState)
        *pState = state;
    if(pResult)
        *pResult = result;
    if(pEvent)
        *pEvent = hEvent;
}

BOOL Future_set_result(Future *self, int state, PyObject *result)
{
    BOOL assigned;
    EnterCriticalSection(&self->lock);
    if(self->state == FUTURE_PENDING)
    {
        self->state = state;
        Py_INCREF(result);
        self->result = result;
        // wake up all the threads that might be calling wait()
        if(self->hEvent)
            SetEvent(self->hEvent);
        assigned = TRUE;
    }
    else
    {
        // the result has already been set
        PyErr_SetString(PyExc_Exception, "The result of the operation has already been set");
        assigned = FALSE;
    }
    LeaveCriticalSection(&self->lock);
    // TODO: call the callback
    return assigned;
}

PyObject * Future_completed(Future *self, PyObject *args)
{
    PyObject *result = Py_None;
    if(!PyArg_ParseTuple(args, "|O", &result))
        return NULL;
    else if(Future_set_result(self, FUTURE_COMPLETED, result))
        Py_RETURN_NONE;
    else
        return NULL;
}

PyObject * Future_after(Future *self, PyObject *args)
{
    return NULL;
}

PyObject * Future_pending_getter(Future *self, void *closure)
{
    int state;
    Future_get_result(self, &state, NULL, NULL);
    if(state == FUTURE_PENDING)
        Py_RETURN_TRUE;
    else
        Py_RETURN_FALSE;
}

PyObject * Future_result_getter(Future *self, void *closure)
{
    PyObject *result, *args = Py_BuildValue("()");
    if(!args)
        return NULL;
    result = Future_wait(self, args);
    Py_DECREF(args);
    return result;
}
