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

def find(resource):
    """ Find a resource file (e.g. icon) and return its path. """
    if sys.platform.lower().startswith("win") and (sys.executable.find("python") < 0):
        return os.path.join(os.path.dirname(sys.executable), resource)
    else:
        path = os.path.join(os.path.dirname(__file__), resource)
        if os.path.exists(path):
            return path
        else:
            return os.path.join("/usr/share/spark", resource)

def iconPath(name, size=None):
    """ Return the path of the specified GNOME icon. """
    if size:
        return find("icons/%ix%i/%s.png" % (size, size, name))
    else:
        return find("icons/scalable/%s.svg" % name)