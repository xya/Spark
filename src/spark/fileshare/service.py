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

from spark.async import Future, Delegate
from spark.messaging import MessengerService, serviceMethod

__all__ = ["FileShare"]

REQ_LIST_FILES = "list-files"
NOT_FILE_ADDED = "file-added"
NOT_FILE_REMOVED = "file-removed"

class FileShare(MessengerService):
    """ Service that shares files over a network. """
    def __init__(self, reactor, name=None):
        super(FileShare, self).__init__(reactor, name)
        self.fileAdded = Delegate()
        self.fileRemoved = Delegate()
        self.remoteNotifications = False
    
    @serviceMethod
    def files(self):
        """ Return the current file table, which maps file IDs to files. """
        return {"123abc" : {"id": "123abc", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}
    
    @serviceMethod
    def addFile(self, path):
        """ Add the local file with the given path to the list. """
        self.fileAdded()
        if self.remoteNotifications and self.isSessionActive:
            self.sendNotification(NOT_FILE_ADDED)
    
    @serviceMethod
    def removeFile(self, fileID):
        """ Remove the file (local or remote) with the given ID from the list. """
        self.fileRemoved()
        if self.remoteNotifications and self.isSessionActive:
            self.sendNotification(NOT_FILE_REMOVED)
    
    def sessionStarted(self):
        self.sendRequest(REQ_LIST_FILES, {'register': True})
    
    def sessionEnded(self):
        pass
    
    def blockReceived(self, m):
        pass
    
    def requestListFiles(self, req):
        """ The remote peer sent a 'list-files' request. """
        if (isinstance(req.params, dict)
            and req.params.has_key("register") and req.params["register"] is True):
            self.remoteNotifications = True
        return {"123abc" : {"id": "123abc", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}
    
    def responselistFiles(self, prev):
        """ The remote peer responded to our 'list-files' request. """
        files = prev.result
        print repr(files)
        # TODO: do something with the file table
    
    def notificationFileAdded(self, n):
        """ The remote peer sent a 'file-added' notification. """
        self.fileAdded()
    
    def notificationFileRemoved(self, n):
        """ The remote peer sent a 'file-removed' notification. """
        self.fileRemoved()