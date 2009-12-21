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
from spark.fileshare.transfers import TransferInfo, TransferLocation

__all__ = ["SharedFile", "FileTable"]

class SharedFile(object):
    """ Represents a file that can be shared between two peers. """
    def __init__(self, name=None, size=None, lastModified=None, mimeType=None, path=None, ID=None):
        self.name = name
        self.size = size
        self.lastModified = lastModified
        self.mimeType = mimeType
        self.path = path
        self.ID = ID
        self.isLocal = False
        self.isRemote = False
        self.localRemoved = False
        self.transfer = None
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"ID": self.ID, "name": self.name, "size": self.size,
                "lastModified": self.lastModified, "mimeType": self.mimeType}
    
    def update(self, info):
        """ Update the information about the file. """
        if isinstance(info, Mapping):
            info = DictWrapper(info)
        self.name = info.name
        self.size = info.size
        self.lastModified = info.lastModified
        self.mimeType = info.mimeType
        self.path = hasattr(info, "path") and info.path or None
    
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
        file.isLocal = True
        file.generateID()
        return file
    
    @property
    def isReceiving(self):
        """ Is the file being received from the remote peer? """
        return self.transfer and (self.transfer.location == TransferLocation.REMOTE) or False
    
    @property
    def isSending(self):
        """ Is the file being sent to the remote peer? """
        return self.transfer and (self.transfer.location == TransferLocation.LOCAL) or False

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
    
    def listFiles(self):
        return self.entries
    
    def addFile(self, path):
        file = SharedFile.fromFile(path)
        self.updateFile(file, True)
    
    def removeFile(self, fileID, local):
        if fileID in self.entries:
            file = self.entries[fileID]
            if local:
                # even if we remove the file from the local list,
                # it might still exist on the peer's list
                file.localRemoved = True
                if not file.isRemote:
                    del self.entries[fileID]
            else:
                # even if the remote peer removed the file from its list,
                # me might have a local copy
                file.isRemote = False
                if not file.isLocal:
                    del self.entries[fileID]
            self.fileRemoved(fileID, local)
            return True
        else:
            return False
    
    def updateFile(self, info, local):
        if hasattr(info, "ID"):
            fileID = info.ID
        else:
            fileID = info["ID"]
        if fileID not in self.entries:
            file = SharedFile()
            file.ID = fileID
            self.entries[fileID] = file
            added = True
        else:
            file = self.entries[fileID]
            added = False
        file.update(info)
        if local:
            file.isLocal = True
        else:
            file.isRemote = True
        if added:
            self.fileAdded(fileID, local)
        else:
            self.fileUpdated(fileID, local)
    
    def updateTable(self, table, local):
        for key, file in table.items():
            self.updateFile(file, local)

class DictWrapper(object):
    def __init__(self, dict):
        self.__dict__.update(dict)