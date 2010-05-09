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

import sys
from PyQt4.QtGui import QPixmap

__all__ = ["from_file", "from_mime_type", "open_file"]

_modules = []
try:
    import gnome
    _modules.append(gnome)
except ImportError:
    pass

try:
    import kde
    _modules.append(kde)
except ImportError:
    pass

try:
    import xdg
    _modules.append(xdg)
except ImportError:
    pass

try:
    import win32
    _modules.append(win32)
except ImportError:
    pass

if _modules:
    _impl = _modules[0]
    for name in __all__:
        setattr(sys.modules[__name__], name, getattr(_impl, name))
else:
    class DummyType(object):
        def __init__(self, mimeType="gtk/file"):
            self.mimeType = mimeType
            self.description = "Unknown file type"
        
        def icon(self, size):
            return QPixmap()
    
    def from_file(path):
        return DummyType()
    
    def from_mime_type(mimeType):
        return DummyType(mimeType)
    
    def open_file(path):
        raise NotImplementedError()