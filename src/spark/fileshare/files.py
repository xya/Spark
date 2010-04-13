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
from collections import Mapping
from spark.async import Delegate
from spark.fileshare.transfers import TransferInfo, UPLOAD, DOWNLOAD

__all__ = ["SharedFile", "FileTable", "FileCopy", "LOCAL", "REMOTE"]

LOCAL = 1
REMOTE = 2

class SharedFile(object):
    """ Represents a file that can be shared between two peers. """
    def __init__(self, name=None, size=None, lastModified=None, mimeType=None, path=None, ID=None):
        self.name = name
        self.size = size
        self.lastModified = lastModified
        self.mimeType = mimeType
        self.path = path
        self.ID = ID
        self.origin = None
        self.localCopy = None
        self.remoteCopy = None
        self.transfer = None
    
    @property
    def localCopySize(self):
        """ Return the completed size of the local copy of the file, or zero if there is no local copy."""
        if self.localCopy:
            return self.localCopy.completedSize
        else:
            return 0
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"ID": self.ID, "name": self.name, "size": self.size,
                "lastModified": self.lastModified, "mimeType": self.mimeType,
                "localCopySize": self.localCopySize}
    
    def __repr__(self):
        return "SharedFile(%s)" % repr(self.__getstate__())
    
    def update(self, info, origin):
        """ Update the information about the file. """
        if isinstance(info, Mapping):
            info = DictWrapper(info)
        self.name = info.name
        self.size = info.size
        self.lastModified = info.lastModified
        self.mimeType = info.mimeType
        self.path = hasattr(info, "path") and info.path or None
        if hasattr(info, "localCopySize"):
            copy = FileCopy(info.size)
            copy.completedSize = info.localCopySize
            if origin == REMOTE:
                self.remoteCopy = copy
            else:
                self.localCopy = copy
    
    def generateID(self):
        """ Generate an unique ID for the file. """
        self.ID = hashlib.md5("%s%d" % (self.name, self.size)).hexdigest()
    
    @classmethod
    def fromFile(cls, path):
        """ Create a shared file from a file path. """
        name = os.path.basename(path)
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        file = cls(name, size)
        file.path = path
        file.lastModified = mtime
        file.generateID()
        return file
    
    @property
    def isReceiving(self):
        """ Is the file being received from the remote peer? """
        return self.transfer and (self.transfer.direction == DOWNLOAD) or False
    
    @property
    def isSending(self):
        """ Is the file being sent to the remote peer? """
        return self.transfer and (self.transfer.direction == UPLOAD) or False
    
    @property
    def isTransfering(self):
        """ Is the file being transfered? """
        return self.isReceiving or self.isSending

class FileCopy(object):
    """ Keep information about a file copy. """
    def __init__(self, originalSize, path=None):
        self.completedSize = 0
        self.originalSize = originalSize
        self.path = path
    
    @property
    def completion(self):
        """ Indicate how complete the copy is compared to the original. """
        if self.originalSize > 0:
            return self.completedSize / self.originalSize
        else:
            return 1.0
    
    @property
    def isComplete(self):
        """ Indicate whether the copy is complete or not. """
        return self.completedSize == self.originalSize

class FileTable(object):
    """ Keep information about shared files, which could be local, remote or both. """
    def __init__(self):
        self.entries = {}
        self.fileAdded = Delegate()
        self.fileUpdated = Delegate()
        self.fileRemoved = Delegate()
    
    def __getitem__(self, fileID):
        try:
            return self.entries[fileID]
        except KeyError:
            return None
    
    @property
    def files(self):
        return self.entries
    
    def addFile(self, path):
        file = SharedFile.fromFile(path)
        file.localCopy = FileCopy(file.size, path)
        file.localCopy.completedSize = file.size
        self.updateFile(file, LOCAL)
    
    def removeFile(self, fileID, origin):
        if fileID in self.entries:
            file = self.entries[fileID]
            if origin == LOCAL:
                # even if we remove the file from the local list,
                # it might still exist on the peer's list
                if not file.remoteCopy:
                    del self.entries[fileID]
                else:
                    file.localCopy = None
            elif origin == REMOTE:
                # even if the remote peer removed the file from its list,
                # we might have a local copy
                if not file.localCopy:
                    del self.entries[fileID]
                else:
                    file.remoteCopy = None
            self.fileRemoved(fileID, origin)
            return True
        else:
            return False
    
    def updateFile(self, info, origin):
        if hasattr(info, "ID"):
            fileID = info.ID
        else:
            fileID = info["ID"]
        if fileID not in self.entries:
            file = SharedFile()
            file.ID = fileID
            file.origin = origin
            self.entries[fileID] = file
            added = True
        else:
            file = self.entries[fileID]
            added = False
        file.update(info, origin)
        if added:
            self.fileAdded(fileID, origin)
        else:
            self.fileUpdated(fileID, origin)
    
    def updateTable(self, table, origin):
        for key, file in table.items():
            self.updateFile(file, origin)

class DictWrapper(object):
    def __init__(self, dict):
        self.__dict__.update(dict)