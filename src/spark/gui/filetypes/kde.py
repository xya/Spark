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
from PyKDE4.kdecore import KMimeType, KUrl
from PyKDE4.kdeui import KIconLoader

__all__ = ["from_file", "from_mime_type", "open_file"]

class KDEType(object):
    def __init__(self, type):
        self._type = type
        self.mimeType = unicode(type.name())
        self.description = unicode(type.comment())
    
    def icon(self, size):
        l = KIconLoader()
        return l.loadMimeTypeIcon(self._type.iconName(), KIconLoader.NoGroup, size) 

def from_file(path):
    """ Try to guess the type of a file. """
    type, confidence = KMimeType.findByPath(path)
    return KDEType(type)

def from_mime_type(mimeType):
    """ Return a file type object matching the given MIME type. """
    type = KMimeType.mimeType(mimeType)
    return KDEType(type)

def open_file(path):
    """ Open the specified file, executing the default application. """
    if not path:
        raise ValueError("The path should be specified")
    elif os.path.exists("/usr/bin/kfmclient"):
        url = KUrl(path)
        subprocess.Popen(["/usr/bin/kfmclient", "exec", unicode(url.url())])
    elif os.path.exists("/usr/bin/xdg-open"):
        subprocess.Popen(["/usr/bin/xdg-open", path])