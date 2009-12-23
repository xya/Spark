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

PyObject * iocp_getResult_read(DWORD error, DWORD bytes, PyObject *data, BOOL *success);
PyObject * iocp_getResult_write(DWORD error, DWORD bytes, PyObject *data, BOOL *success);

#endif