/*
 Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>

 This file is part of the Spark File-transfer Tool.

 Spark is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 Spark is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with Spark; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
*/

#ifndef PYTHON_IOCP
#define PYTHON_IOCP

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_lastwin32error(const char *format);
void iocp_win32error(DWORD error, const char *format);
PyObject * iocp_createWinError(DWORD error, const char *format);
PyObject * iocp_fetchException();
BOOL iocp_createAsyncPipe(PHANDLE hRead, PHANDLE hWrite);
void iocp_addConstant(PyObject *module, char *name, DWORD value);
PyObject * iocp_allocBuffer(Py_ssize_t size, void **pBuffer);

// Type of operations handled by the completion port
#define OP_THROW        0
#define OP_INVOKE       1
#define OP_READ         2
#define OP_WRITE        3
#define OP_CONNECT      4
#define OP_ACCEPT       5

#endif