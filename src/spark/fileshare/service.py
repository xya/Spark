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

from collections import Mapping

from spark.async import Future, Delegate
from spark.messaging import Service
from spark.fileshare import SharedFile, FileTable

__all__ = ["FileShare"]

REQ_LIST_FILES = "list-files"
NOT_FILE_ADDED = "file-added"
NOT_FILE_REMOVED = "file-removed"

class FileShare(Service):
    """ Service that shares files over a network. """
    def __init__(self, session, name=None):
        super(FileShare, self).__init__(session, name)
        self.filesUpdated = Delegate()
        self.remoteNotifications = False
        self.fileTable = FileTable()
        self.fileTable.fileAdded += self.cacheFileAdded
        self.fileTable.fileUpdated += self.cacheFileUpdated
        self.fileTable.fileRemoved += self.cacheFileRemoved
        session.registerService(self)
    
    def files(self, excludeRemoved=True):
        """ Return a copy of the current file table, which maps file IDs to files. """
        cache = self.fileTable.listFiles()
        if excludeRemoved:
            files = {}
            for fileID, file in cache.items():
                if not file.localRemoved:
                    files[fileID] = file
            return files
        else:
            return cache.copy()

    def addFile(self, path):
        """ Add the local file with the given path to the list. """
        self.fileTable.addFile(path)
    
    def removeFile(self, fileID):
        """ Remove the file (local or remote) with the given ID from the list. """
        self.fileTable.removeFile(fileID, True)
    
    def cacheFileAdded(self, fileID, local):
        self.filesUpdated()
        if local and self.remoteNotifications and self.session.isActive:
            file = self.fileTable[fileID]
            self.sendNotification(NOT_FILE_ADDED, file)
    
    def cacheFileUpdated(self, fileID, local):
        self.filesUpdated()
    
    def cacheFileRemoved(self, fileID, local):
        self.filesUpdated()
        if local and self.remoteNotifications and self.session.isActive:
            self.sendNotification(NOT_FILE_REMOVED, fileID)
    
    def start(self):
        """ Start the service. The session must be currently active. """
        self.sendRequest(REQ_LIST_FILES, {'register': True})
    
    def stop(self):
        """ Stop the service, probably because the session ended. """
        pass
    
    def requestListFiles(self, req):
        """ The remote peer sent a 'list-files' request. """
        if (isinstance(req.params, Mapping)
            and "register" in req.params and req.params["register"] is True):
            self.remoteNotifications = True
        return self.fileTable.listFiles()
    
    def responselistFiles(self, prev):
        """ The remote peer responded to our 'list-files' request. """
        files = prev.result
        self.fileTable.updateTable(files, False)
    
    def notificationFileAdded(self, n):
        """ The remote peer sent a 'file-added' notification. """
        if isinstance(n.params, Mapping):
            self.fileTable.updateFile(n.params, False)
    
    def notificationFileRemoved(self, n):
        """ The remote peer sent a 'file-removed' notification. """
        if isinstance(n.params, Mapping) and "ID" in n.params:
            self.fileTable.removeFile(n.params["ID"], False)