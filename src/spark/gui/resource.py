# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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
import os

__all__ = ["find", "iconPath"]

def find(resource, pathHints=[]):
    """ Find a resource file (e.g. icon) and return its path. """
    if not resource:
        return None
    paths = []
    paths.extend(pathHints)
    if sys.platform.lower().startswith("win") and (sys.executable.find("python") < 0):
        paths.append(os.path.dirname(sys.executable))
    paths.append(os.path.dirname(__file__))
    paths.append("/usr/share/spark")
    for path in paths:
        file = os.path.join(path, resource)
        if os.path.exists(file):
            return file

def iconPath(name, size=None):
    """ Return the path of the specified GNOME icon. """
    if size:
        file = "%ix%i/%s.png" % (size, size, name)
    else:
        file = "scalable/%s.svg" % name
    return _findGnomeIconFile(file)

def _findGnomeIconFile(file):
    path = find("icons/%s" % file)
    if path:
        return path
    else:
        pathHints = ["/usr/share/icons/gnome"]
        return find(file, pathHints)