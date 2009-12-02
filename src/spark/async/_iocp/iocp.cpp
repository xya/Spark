#include <Python.h>
#include <stdio.h>
#include "iocp.h"

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

static PyMethodDef Overlapped_methods[] =
{
    {"address", (PyCFunction)Overlapped_address, METH_NOARGS, "Return the address of the OVERLAPPED structure."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyMethodDef CompletionPort_methods[] =
{
    {"close",  CompletionPort_close, METH_VARARGS, "Close the completion port."},
    {"register",  CompletionPort_register, METH_VARARGS, "Register a file with the completion port and return its tag."},
    {"overlapped",  CompletionPort_overlapped, METH_VARARGS, 
    "Create an OVERLAPPED struct, eventually wrapping some objects, \
and return a pointer to the struct. The objects will be returned, \
and the structure freed by wait()."},
    {"freeOverlapped",  CompletionPort_freeOverlapped, METH_VARARGS, 
    "Free the OVERLAPPED structure when wait() will not be called \
(e.g. the asynchronous call failed), and return the wrapped objects."},
    {"post",  CompletionPort_post, METH_VARARGS, "Directly post the objects to the completion port."},
    {"wait",  CompletionPort_wait, METH_VARARGS, 
    "Wait for an operation to be finished and return a (ID, tag, bytes, objs) \
tuple containing the result. The OVERLAPPED structure is also freed. "},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static PyTypeObject CompletionPortType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.CompletionPort",                                 /*tp_name*/
    sizeof(CompletionPort),                                 /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    (destructor)CompletionPort_dealloc,                     /*tp_dealloc*/
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
    "Completion port objects",                              /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    CompletionPort_methods,                                 /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    (initproc)CompletionPort_init,                          /* tp_init */
    0,                                                      /* tp_alloc */
    CompletionPort_new,                                     /* tp_new */
};

static PyTypeObject OverlappedType =
{
    PyObject_HEAD_INIT(NULL)
    0,                                                      /*ob_size*/
    "_iocp.Overlapped",                                     /*tp_name*/
    sizeof(Overlapped),                                     /*tp_basicsize*/
    0,                                                      /*tp_itemsize*/
    0,                                                      /*tp_dealloc*/
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
    "Overlapped objects",                                   /* tp_doc */
    0,		                                                /* tp_traverse */
    0,		                                                /* tp_clear */
    0,		                                                /* tp_richcompare */
    0,		                                                /* tp_weaklistoffset */
    0,		                                                /* tp_iter */
    0,		                                                /* tp_iternext */
    Overlapped_methods,                                     /* tp_methods */
    0,                                                      /* tp_members */
    0,                                                      /* tp_getset */
    0,                                                      /* tp_base */
    0,                                                      /* tp_dict */
    0,                                                      /* tp_descr_get */
    0,                                                      /* tp_descr_set */
    0,                                                      /* tp_dictoffset */
    (initproc)Overlapped_init,                              /* tp_init */
    0,                                                      /* tp_alloc */
    Overlapped_new,                                         /* tp_new */
};

PyMODINIT_FUNC init_iocp(void)
{
    PyObject *m;

    if(PyType_Ready(&OverlappedType) < 0)
        return;

    if(PyType_Ready(&CompletionPortType) < 0)
        return;

    m = Py_InitModule3("_iocp", iocp_Methods,
       "Wrapper around Windows' I/O completion port interface");

    Py_INCREF(&OverlappedType);
    PyModule_AddObject(m, "Overlapped", (PyObject *)&OverlappedType);

    Py_INCREF(&CompletionPortType);
    PyModule_AddObject(m, "CompletionPort", (PyObject *)&CompletionPortType);
}

void iocp_win32error(PyTypeObject *excType, const char *format)
{
    char message[512], text[512];
    ZeroMemory(message, sizeof(message));
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM, 0, GetLastError(), LANG_NEUTRAL, 
        message, sizeof(message), 0);
    if(format)
    {
        snprintf(text, sizeof(text), format, message);
        PyErr_SetString(excType, text);
    }
    else
    {
        PyErr_SetString(excType, message);
    }
}

void Overlapped_dealloc(Overlapped* self)
{
    Py_CLEAR(self->self);
    Py_CLEAR(self->data);
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * Overlapped_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Overlapped *self = (Overlapped *)type->tp_alloc(type, 0);
    if(self != NULL)
    {
        ZeroMemory(&self->ov, sizeof(OVERLAPPED));
        self->self = self;
        Py_INCREF(self->self);
        self->data = Py_None;
        Py_INCREF(self->data);
    }
    return (PyObject *)self;
}

int Overlapped_init(Overlapped *self, PyObject *args, PyObject *kwds)
{
    PyObject *old;

    if(!PyTuple_Check(args))
        return -1;
    old = self->data;
    Py_INCREF(args);
    self->data = args;
    Py_DECREF(old);
    return 0;
}

PyObject * Overlapped_address(Overlapped *self)
{
    return Py_BuildValue("n", &self->ov);
}

void CompletionPort_dealloc(CompletionPort* self)
{
    if(self->hPort)
    {
        CloseHandle(self->hPort);
        self->hPort = 0;
    }
    self->ob_type->tp_free((PyObject*)self);
}

PyObject * CompletionPort_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    CompletionPort *self = (CompletionPort *)type->tp_alloc(type, 0);
    if(self != NULL)
        self->hPort = 0;
    return (PyObject *)self;
}

int CompletionPort_init(CompletionPort *self, PyObject *args, PyObject *kwds)
{
    if(!PyArg_ParseTuple(args, ""))
        return -1;
    self->hPort = CreateIoCompletionPort(INVALID_HANDLE_VALUE, NULL, (ULONG_PTR)NULL, 0);
    if(!self->hPort)
        iocp_win32error(PyExc_Exception, "Could not create completion port (%s)");
    return 0;
}

PyObject * CompletionPort_close(CompletionPort *self, PyObject *args)
{
    if(!PyArg_ParseTuple(args, ""))
        return NULL;

    if(self->hPort)
    {
        CloseHandle(self->hPort);
        self->hPort = 0;
    }
    Py_RETURN_NONE;
}

PyObject * CompletionPort_register(CompletionPort *self, PyObject *args)
{
    Py_ssize_t hFile;
    if(!PyArg_ParseTuple(args, "n", &hFile))
        return NULL;
    if(!CreateIoCompletionPort((HANDLE)hFile, self->hPort, (HANDLE)hFile, 0))
    {
        iocp_win32error(PyExc_Exception, "Could not register file (%s)");
        return NULL;
    }
    return Py_BuildValue("n", hFile);
}

PyObject * CompletionPort_overlapped(CompletionPort *self, PyObject *args)
{
    Overlapped *over, *ovargs, *ovkw;
    int ret;

    ovargs = Py_BuildValue("()");
    if(!ovargs)
        return NULL;

    ovkw = Py_BuildValue("{}");
    if(!ovkw)
    {
        Py_DECREF(ovargs);
        return NULL;
    }

    over = Overlapped_new(&OverlappedType, ovargs, ovkw);
    if(!over)
    {
        Py_DECREF(ovargs);
        Py_DECREF(ovkw);
        return NULL;
    }

    ret = Overlapped_init(over, ovargs, ovkw);
    Py_DECREF(ovargs);
    Py_DECREF(ovkw);
    if(ret != 0)
    {
        Py_DECREF(over);
        return NULL;
    }
    return over;
}

PyObject * CompletionPort_freeOverlapped(CompletionPort *self, PyObject *args)
{
    PyObject *ov;
    if (!PyArg_ParseTuple(args, "O", &ov))
        return NULL;
    Py_RETURN_NONE;
}

PyObject * CompletionPort_post(CompletionPort *self, PyObject *args)
{
    /*
    def post(self, *objs):
        """ Directly post the objects to the completion port. """
        win32.PostQueuedCompletionStatus(self.handle,
            0, win32.INVALID_HANDLE_VALUE, self.overlapped(*objs))
    */
    if(!PyTuple_Check(args))
        return -1;
    Py_RETURN_NONE;
} 
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args)
{
    /*
    def wait(self):
        """
        Wait for an operation to be finished and return a (ID, tag, bytes, objs)
        tuple containing the result. The OVERLAPPED structure is also freed. 
        """
        bytes = c_uint32()
        tag = c_void_p(0)
        lpOver = cast(0, win32.LP_OVERLAPPED)
        win32.GetQueuedCompletionStatus(self.handle,
            byref(bytes), byref(tag), byref(lpOver), -1)
        refID = lpOver.contents.UserData
        win32.freeOVERLAPPED(lpOver)
        if refID > 0:
            with self.lock:
                userData = self.refs.pop(refID)
        else:
            userData = ()
        return refID, tag.value, bytes.value, userData
    */
    const char *text;
    if (!PyArg_ParseTuple(args, "s", &text))
        return NULL;
    printf("%s\n", text);
    Py_RETURN_NONE;
}
