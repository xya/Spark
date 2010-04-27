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

import os
import hashlib
import types
from copy import deepcopy
from collections import Mapping
from datetime import datetime, timedelta
from spark.core import *

__all__ = ["SharedFile", "FileTable", "LOCAL", "REMOTE",
           "TransferInfo", "TransferTable", "UPLOAD", "DOWNLOAD",
           "formatSize", "formatDuration"]

LOCAL = 1
REMOTE = 2

UPLOAD = 1        # a local file is being sent
DOWNLOAD = 2      # a remote file is being received

Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
def formatSize(size, format="%s"):
    if size is None:
        return "n/a"
    for unit, count in reversed(Units):
        if size >= count:
            return format % ("%0.2f %s" % (size / float(count), unit))
    return format % ("%d byte" % size)

SecInMinute = 60.0
SecInHour = 60.0 * 60.0
SecInDay = 60.0 * 60.0 * 24.0
def formatDuration(seconds):
    if seconds is None:
        return "n/a"
    elif seconds < 1.0:
        return "<1 second"
    elif seconds < SecInMinute:
        return "%d seconds" % int(seconds)
    elif seconds < SecInHour:
        return "%.1f minutes" % (seconds / SecInMinute)
    elif seconds < SecInDay:
        return "%.1f hours" % (seconds / SecInHour)
    else:
        return "%.1f days" % (seconds / SecInDay)

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
        self.localCopySize = None
        self.remoteCopySize = None
        self.transfer = None
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"ID": self.ID, "name": self.name, "size": self.size,
                "lastModified": self.lastModified, "mimeType": self.mimeType,
                "localCopySize": self.localCopySize}
    
    def __repr__(self):
        return "SharedFile(%s)" % repr(self.__getstate__())
    
    def copy(self, includeTransfer=True):
        """ Return a copy of the file information. """
        newFile = SharedFile()
        newFile.name = self.name
        newFile.size = self.size
        newFile.lastModified = self.lastModified
        newFile.mimeType = self.mimeType
        newFile.path = self.path
        newFile.ID = self.ID
        newFile.origin = self.origin
        newFile.localCopySize = self.localCopySize
        newFile.remoteCopySize = self.remoteCopySize
        if includeTransfer and self.transfer:
            newFile.transfer = self.transfer.copy()
        return newFile

    def generateID(self):
        """ Generate an unique ID for the file. """
        tag = u"%s%d" % (self.name, self.size)
        self.ID = hashlib.md5(tag.encode("utf8")).hexdigest()

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
        return (self.transfer
            and (self.transfer.direction == DOWNLOAD)
            and (self.transfer.state == "active")
            or False)
    
    @property
    def isSending(self):
        """ Is the file being sent to the remote peer? """
        return (self.transfer
                and (self.transfer.direction == UPLOAD)
                and (self.transfer.state == "active")
                or False)
    
    @property
    def isTransfering(self):
        """ Is the file being transfered? """
        return self.isReceiving or self.isSending
    
    def hasCopy(self, origin):
        """ Determine whether there is a local or remote copy of the file. """
        return self.completedSize(origin) is not None
    
    def completedSize(self, origin):
        """ Indicate how complete a copy is compared to the original. """
        if origin == LOCAL:
            return self.localCopySize
        elif origin == REMOTE:
            return self.remoteCopySize
        else:
            raise ValueError("Invalid file origin")
    
    def completion(self, origin):
        """ Indicate how complete a copy is compared to the original. """
        if self.size > 0:
            return float(self.completedSize(origin)) / float(self.size)
        else:
            return 1.0

    def isComplete(self, origin):
        """ Indicate whether a copy is complete or not. """
        return self.completedSize(origin) == self.size

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
    
    def clearTransfers(self):
        remove = []        
        for fileID, file in self.entries.items():
            file.transfer = None
            file.remoteCopySize = None
            if file.localCopySize is None:
                remove.append(fileID)
        for fileID in remove:
            file = self.entries[fileID]
            del self.entries[fileID]
            self.fileRemoved(fileID, file.origin)
            
    @property
    def files(self):
        return self.entries
    
    def addFile(self, path):
        file = SharedFile.fromFile(path)
        file.localCopySize = file.size
        self.updateFile(file, LOCAL)
    
    def removeFile(self, fileID, origin):
        if fileID in self.entries:
            file = self.entries[fileID]
            if origin == LOCAL:
                # even if we remove the file from the local list,
                # it might still exist on the peer's list
                if file.hasCopy(REMOTE):
                    file.localCopy = None
                else:
                    del self.entries[fileID]
            elif origin == REMOTE:
                # even if the remote peer removed the file from its list,
                # we might have a local copy
                if file.hasCopy(LOCAL):
                    file.remoteCopy = None
                else:
                    del self.entries[fileID]
            self.fileRemoved(fileID, origin)
            return True
        else:
            return False
    
    def updateFile(self, info, origin):
        if isinstance(info, Mapping):
            info = DictWrapper(info)
        fileID = info.ID
        if fileID not in self.entries:
            file = SharedFile()
            file.origin = origin
            self.entries[fileID] = file
            added = True
        else:
            file = self.entries[fileID]
            added = False
        # update file attributes
        if origin == file.origin:
            # same origin, we can copy most attributes
            attributes = ("name", "size", "lastModified", "mimeType", "path", "ID")
            for name in (attr for attr in attributes if hasattr(info, attr)):
                setattr(file, name, getattr(info, name))
            if origin == LOCAL:
                file.localCopySize = info.localCopySize
        if origin == REMOTE:
            file.remoteCopySize = info.localCopySize
        if added:
            self.fileAdded(fileID, origin)
        else:
            self.fileUpdated(fileID, origin)
    
    def updateTable(self, table, origin):
        for key, file in table.items():
            self.updateFile(file, origin)

class TransferInfo(object):
    """ Provides information about a file transfer. """
    def __init__(self, transferID, direction, fileID, pid):
        self.transferID = transferID
        self.direction = direction
        self.fileID = fileID
        self.pid = pid
        self.state = "created"
        self.completedSize = 0
        self.originalSize = 0
        self.transferSpeed = 0
        self.started = None
        self.ended = None
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"transferID": self.transferID, "fileID": self.fileID, "state": self.state}
    
    def __repr__(self):
        attr = ["%s=%s" % (name, repr(getattr(self, name)))
                for name in ("state", "progress")]
        return "TransferInfo(%s)" % ", ".join(attr) 
    
    def copy(self):
        """ Return a copy of the object. """
        newTransfer = TransferInfo(self.transferID, self.direction, self.fileID, self.pid)
        newTransfer.state = self.state
        newTransfer.completedSize = self.completedSize
        newTransfer.originalSize = self.originalSize
        newTransfer.transferSpeed = self.transferSpeed
        newTransfer.started = self.started
        newTransfer.ended = self.ended
        return newTransfer
    
    def updateState(self, info):
        self.state = info.state
        self.completedSize = info.completedSize
        self.originalSize = info.originalSize
        self.transferSpeed = info.transferSpeed
        self.started = info.started
        self.ended = info.ended
    
    @property
    def duration(self):
        """ Return the duration of the transfer, or None if the transfer has never been started. """
        if self.started is None:
            return None
        elif self.ended is None:
            return datetime.now() - self.started
        else:
            return self.ended - self.started
    
    @property
    def totalSeconds(self):
        """ Same than duration, but in seconds. """
        duration = self.duration
        if duration is None:
            return None
        else:
            seconds = duration.seconds
            seconds += (duration.microseconds * 10e-7)
            seconds += (duration.days * 24 * 3600)
            return seconds
    
    @property
    def averageSpeed(self):
        """ Return the average transfer speed, in bytes/s. """
        seconds = self.totalSeconds
        if seconds is None:
            return None
        else:
            return self.completedSize / seconds
    
    @property
    def progress(self):
        """ Return a number between 0.0 and 1.0 indicating the progress of the transfer. """
        if self.originalSize:
            return float(self.completedSize) / float(self.originalSize)
        else:
            return None
    
    @property
    def left(self):
        """ Return an estimation of the time left before the transfer is complete, in seconds. """
        progress = self.progress
        seconds = self.totalSeconds
        if (progress is None) or (seconds is None) or (progress == 0.0):
            return None
        else:
            return (seconds / progress) - seconds

class TransferTable(object):
    def __init__(self):
        self.entries = {}
    
    def __iter__(self):
        return self.entries.itervalues()
    
    def find(self, transferID, direction):
        try:
            return self.entries[(transferID, direction)]
        except KeyError:
            return None
    
    def createTransfer(self, transferID, direction, fileID, pid):
        transfer = TransferInfo(transferID, direction, fileID, pid)
        self.entries[(transferID, direction)] = transfer
        return transfer
    
    def clear(self):
        for transfer in self.entries.values():
            Process.try_send(transfer.pid, Command("stop"))
        self.entries.clear()

class DictWrapper(object):
    def __init__(self, dict):
        self.__dict__.update(dict)