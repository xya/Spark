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

import os
import subprocess
import gio
import gtk
from PyQt4.QtGui import QPixmap

__all__ = ["from_file", "from_mime_type_or_extension"]

class GnomeType(object):
    def __init__(self, type):
        self._type = type
        self.mimeType = gio.content_type_get_mime_type(type)
        self.description = gio.content_type_get_description(type)
    
    def icon(self, size):
        iconName = gio.content_type_get_icon(self._type)
        theme = gtk.icon_theme_get_default()
        icon = theme.choose_icon(iconName.get_names(), size, 0)
        if icon:
            return QPixmap(icon.get_filename())
        else:
            return QPixmap()

def from_file(path):
    """ Try to guess the type of a file. """
    try:
        with open(path, "rb") as f:
            header = f.read(256)
            size = len(header)
    except IOError:
        header = None
        size = 0
    type, confidence = gio.content_type_guess(path, header, size)
    return GnomeType(type)

def from_mime_type_or_extension(mimeType, extension):
    """ Return a file type object matching the given MIME type and/or extension. """
    if not mimeType and not extension:
        raise ValueError("At least the MIME type or extension should be specified")
    elif not mimeType:
        type, confidence = gio.content_type_guess("foo" + extension, None, 0)
        return GnomeType(type)
    else:
        type = gio.content_type_from_mime_type(mimeType)
        return GnomeType(type)