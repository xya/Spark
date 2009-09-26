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
from spark.fileshare.common import TransferInfo, TransferLocation
from spark.fileshare.session import FileShareSession

class SharedList(object):
    """ Represents a list of files that can be shared between two peers. """
    def __init__(self):
        self.session = FileShareSession()
        self.updated = Delegate()
        self.files = {}
        self.order = []
    
    @property
    def isConnected(self):
        """ Is the file list connected to a remote peer? """
        return self.session.isActive
    
    def connect(self, address):
        """ Connect the file list to a remote peer. """
        self.session.connect(address)
    
    def listen(self, address):
        """ Wait for a peer to connect to the file list. """
        self.session.listen(address)
    
    def disconnect(self):
        """ Disconnect the file list from the connected peer. """
        self.session.disconnect()
    
    def __iter__(self):
        """ Iterate over the files in the list. """
        return (self.files[ID] for ID in self.order)
    
    def __getitem__(self, index):
        """ Return the file at the specified index. """
        if (index >= 0) and (index < len(self.order)):
            return self.files[self.order[index]]
        else:
            return None
    
    @property
    def activeTransfers(self):
        """ Return the number of active transfers in the list. """ 
        count = 0
        for file in self.files.itervalues():
            if file.transfer:
                count += 1
        return count
    
    @property
    def downloadSpeed(self):
        """ Return the current download speed, in bytes per second. """
        return 0
    
    @property
    def uploadSpeed(self):
        """ Return the current upload speed, in bytes per second. """
        return 0
    
    def addLocalFile(self, path):
        """ Add a local file to the list. """
        self.addFile(SharedFile.fromFile(path))
    
    def addFile(self, file):
        """ Add a SharedFile instance to the list. """
        ID = file.ID
        if not self.files.has_key(ID):
            self.order.append(ID)
        self.files[ID] = file
        self.updated()
    
    def removeFile(self, file):
        """ Remove the file from the list. """
        if hasattr(file, "ID"):
            file = file.ID
        if self.files.has_key(file):
            del self.files[file]
            self.order.remove(file)
            self.updated()
            return True
        else:
            return False
    
    def isActionAvailable(self, name, file=None):
        """ Can the specified action be used now? """
        if isinstance(file, basestring):
            file = self.files[file]
        if name == "add":
            return True
        elif file is None:
            return False
        elif name == "remove":
            return self.files.has_key(file.ID)
        elif name == "start":
            return file.isRemote
        elif name == "pause":
            return file.isReceiving or file.isSending
        elif name == "stop":
            return file.isReceiving or file.isSending
        elif name == "open":
            return file.isLocal
        else:
            return False

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
    
    def startTransfer(self):
        raise NotImplementedError()
    
    def stopTransfer(self):
        raise NotImplementedError()
    
    def open(self):
        raise NotImplementedError()