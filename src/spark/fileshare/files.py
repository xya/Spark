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

import os
import hashlib
from spark.async import Delegate
from spark.fileshare.transfers import TransferInfo, TransferLocation

__all__ = ["SharedFile"]

class SharedFile(object):
    """ Represents a file that can be shared between two peers. """
    def __init__(self, name, size, lastModified=None, mimeType=None, path=None, ID=None):
        self.name = name
        self.size = size
        self.lastModified = lastModified
        self.mimeType = mimeType
        self.path = path
        if ID:
            self.ID = ID
        else:
            self.ID = hashlib.md5("%s%d" % (name, size)).hexdigest()
        self.transfer = None
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"ID": self.ID, "name": self.name, "size": self.size,
                "lastModified": self.lastModified, "mimeType": self.mimeType}
    
    @classmethod
    def fromFile(cls, path):
        """ Create a shared file from a file path. """
        name = os.path.basename(path)
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        file = cls(name, size)
        file.path = path
        file.lastModified = mtime
        return file
    
    @property
    def isLocal(self):
        """ Is the file is available locally, even partially? """
        return self.path and os.path.exists(self.path) or False
    
    @property
    def isRemote(self):
        """ Is the file is available remotely, even partially? """
        return not self.isLocal or self.isSending
    
    @property
    def isReceiving(self):
        """ Is the file being received from the remote peer? """
        return self.transfer and (self.transfer.location == TransferLocation.REMOTE) or False
    
    @property
    def isSending(self):
        """ Is the file being sent to the remote peer? """
        return self.transfer and (self.transfer.location == TransferLocation.LOCAL) or False