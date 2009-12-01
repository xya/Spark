#ifndef PYTHON_IOCP
#define PYTHON_IOCP

#include <windows.h>
#include <stdio.h>

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
PyObject * iocp_printf(PyObject *self, PyObject *args);

#endif