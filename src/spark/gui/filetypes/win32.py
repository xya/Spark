# -*- coding: utf-8 -*-
#
# Copyright (C) 22010 Pierre-André Saulais <pasaulais@free.fr>
#
# This file is part of the Spark File-transfer Tool.
#
# Spark is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Spark is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Spark; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import mimetypes
import os
from ctypes import windll, WinError, Structure, byref, sizeof, POINTER
from ctypes import c_void_p, c_uint32, c_int32, c_wchar, c_wchar_p
from PyQt4.QtGui import QPixmap

__all__ = ["from_file", "from_mime_type", "open_file"]

class SHFILEINFO(Structure):
    _fields_ = [("hIcon", c_void_p),
                ("iIcon", c_int32),
                ("dwAttributes", c_uint32),
                ("szDisplayName", c_wchar * 260),
                ("szTypeName", c_wchar * 80)]

class SHGFI(object):
    SHGFI_ICON = 0x100
    SHGFI_DISPLAYNAME = 0x200
    SHGFI_TYPENAME = 0x400
    SHGFI_ATTRIBUTES = 0x800
    SHGFI_ICONLOCATION = 0x1000
    SHGFI_EXETYPE = 0x2000
    SHGFI_SYSICONINDEX = 0x4000
    SHGFI_LINKOVERLAY = 0x8000
    SHGFI_SELECTED = 0x10000
    SHGFI_ATTR_SPECIFIED = 0x20000
    SHGFI_LARGEICON = 0x0
    SHGFI_SMALLICON = 0x1
    SHGFI_OPENICON = 0x2
    SHGFI_SHELLICONSIZE = 0x4
    SHGFI_USEFILEATTRIBUTES = 0x10
    SHGFI_ADDOVERLAYS = 0x20
    SHGFI_OVERLAYINDEX = 0x40
    SHIL_LARGE = 0x0
    SHIL_SMALL = 0x1
    SHIL_EXTRALARGE = 0x2
    SHIL_SYSSMALL = 0x3
    SHIL_JUMBO = 0x4

FILE_ATTRIBUTE_NORMAL = 0x0080

IID_IImageList = "46EB5926-582E-4017-9FDF-E8998DAA0950"

SHGetFileInfo = windll.shell32.SHGetFileInfoW
SHGetFileInfo.argtypes = [c_wchar_p, c_uint32, POINTER(SHFILEINFO), c_uint32, c_uint32]
SHGetFileInfo.restype = c_int32

SHGetImageList = windll.shell32.SHGetImageList
SHGetImageList.argtypes = [c_int32, c_void_p, POINTER(c_void_p)]
SHGetImageList.restype = c_uint32

ImageList_GetIcon = windll.comctl32.ImageList_GetIcon
ImageList_GetIcon.argtypes = [c_void_p, c_int32, c_uint32]
ImageList_GetIcon.restype = c_void_p

DestroyIcon = windll.user32.DestroyIcon
DestroyIcon.argtypes = [c_void_p]
DestroyIcon.restype = c_int32

def GetFileInfo(path, flags):
    info = SHFILEINFO()
    if 0 == SHGetFileInfo(path, FILE_ATTRIBUTE_NORMAL, byref(info), sizeof(info), flags):
        raise WinError()
    else:
        return info

class Win32Type(object):
    def __init__(self, extension, mimeType, description):
        self._extension = extension
        self.mimeType = mimeType
        self.description = description
    
    def icon(self, size):
        flags = SHGFI.SHGFI_USEFILEATTRIBUTES | SHGFI.SHGFI_ICON
        if size < 32:
            flags = flags | SHGFI.SHGFI_SMALLICON
        else:
            flags = flags | SHGFI.SHGFI_LARGEICON
        info = GetFileInfo(self._extension, flags)
        px = QPixmap.fromWinHICON(info.hIcon)
        DestroyIcon(info.hIcon)
        return px

def from_file(path):
    """ Try to guess the type of a file. """
    root, extension = os.path.splitext(path)
    info = GetFileInfo(extension, SHGFI.SHGFI_TYPENAME | SHGFI.SHGFI_USEFILEATTRIBUTES)
    mimeType, encoding = mimetypes.guess_type(path)
    return Win32Type(extension, mimeType, info.szTypeName)

def from_mime_type(mimeType):
    """ Return a file type object matching the given MIME type. """
    extension = mimetypes.guess_extension(mimeType)
    info = GetFileInfo(extension, SHGFI.SHGFI_TYPENAME | SHGFI.SHGFI_USEFILEATTRIBUTES)
    return Win32Type(extension, mimeType, info.szTypeName)

def open_file(path):
    """ Open the specified file, executing the default application. """
    if not path:
        raise ValueError("The path should be specified")
    raise NotImplementedError()