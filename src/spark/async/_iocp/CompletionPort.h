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
PyObject * CompletionPort_post(CompletionPort *self, DWORD opcode, PyObject *cont, PyObject *data);
PyObject * CompletionPort_invokeLater(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_throw(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_wait(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_getResult(CompletionPort *self,
        DWORD error, DWORD bytes, DWORD opcode, PyObject *cont, PyObject *data);
PyObject * iocp_getResult_invoke(DWORD error, DWORD bytes, PyObject *data, BOOL *success);
PyObject * iocp_getResult_throw(DWORD error, DWORD bytes, PyObject *data, BOOL *success);
PyObject * CompletionPort_createFile(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createPipe(CompletionPort *self, PyObject *args);
PyObject * CompletionPort_createAsyncFile(CompletionPort *self, HANDLE hFile);
PyObject * CompletionPort_createSocket(CompletionPort *self, PyObject *args);
BOOL CompletionPort_registerFile(CompletionPort *self, HANDLE hFile);

#endif