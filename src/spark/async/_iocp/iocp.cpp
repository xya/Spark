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

static PyMethodDef IOCPMethods[] = {
    {"printf",  iocp_printf, METH_VARARGS, "Print a message to the screen"},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

PyMODINIT_FUNC init_iocp(void)
{
    (void)Py_InitModule("_iocp", IOCPMethods);
}

PyObject * iocp_printf(PyObject *self, PyObject *args)
{
    const char *text;
    if (!PyArg_ParseTuple(args, "s", &text))
        return NULL;
    printf("%s\n", text);
    Py_INCREF(Py_None);
    return Py_None;
}
