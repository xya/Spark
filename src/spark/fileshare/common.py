# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>
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

from spark.async import Delegate

class FileShare(object):
    """ Base class for interacting with Spark file shares. """
    def __init__(self):
        self.fileAdded = Delegate()
        self.fileRemoved = Delegate()
        self.transferStateChanged = Delegate()
        self.panic = Delegate()
    
    def listFiles(self, params, future):
        """ Return the current list of shared files. """
        raise NotImplementedError()
    
    def createTransfer(self, params, future):
        """ Create a transfer of a file's blocks. """
        raise NotImplementedError()
    
    def startTransfer(self, params, future):
        """ Start an inactive transfer. """
        raise NotImplementedError()
    
    def closeTransfer(self, params, future):
        """ Terminate an existing transfer. """
        raise NotImplementedError()
    
    def shutdown(self, params, futue):
        """ Shut down the file share, terminating all transfers. """
        raise NotImplementedError()

def toCamelCase(tag, capitalizeFirst=False):
    """ Convert the tag to camel case (e.g. "create-transfer" becomes "createTransfer"). """
    words = tag.split("-")
    first = words.pop(0)
    words = [word.capitalize() for word in words]
    words.insert(0, first)
    return "".join(words)