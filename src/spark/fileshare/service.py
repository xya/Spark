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

from spark.async import Future, Delegate, coroutine
from spark.messaging import Service
from spark.fileshare import SharedFile, FileTable, TransferTable, UPLOAD, DOWNLOAD

__all__ = ["FileShare"]

REQ_LIST_FILES = "list-files"
REQ_CREATE_TRANSFER = "create-transfer"
REQ_START_TRANSFER = "start-transfer"
NOT_FILE_ADDED = "file-added"
NOT_FILE_REMOVED = "file-removed"
NOT_TRANSFER_STATE_CHANGED = "transfer-state-changed"

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
        self.transferTable = TransferTable()
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
    
    @coroutine
    def startTransfer(self, fileID):
        """ Start receiving the remote file with the given ID. """
        file = self.fileTable[fileID]
        if file.transfer is None:
            resp = yield self.sendRequest(REQ_CREATE_TRANSFER, {"fileID": fileID})
            transferID = resp.params.get("transferID")
            file = self.fileTable[resp.params.get("fileID")]
            transfer = self.transferTable.createTransfer(transferID, DOWNLOAD)
            transfer.fileID = file.ID
            file.transfer = transfer
            self.filesUpdated()
        yield self.sendRequest(REQ_START_TRANSFER, {"transferID": transferID})
    
    def stopTransfer(self, fileID):
        """ Stop receiving the remote file with the given ID. """
        raise NotImplementedError()
    
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
            self.sendNotification(NOT_FILE_REMOVED, {"ID": fileID})
    
    @coroutine
    def start(self):
        """ Start the service. The session must be currently active. """
        resp = yield self.sendRequest(REQ_LIST_FILES, {'register': True})
        self.fileTable.updateTable(resp.params, False)
        
    def stop(self):
        """ Stop the service, probably because the session ended. """
        pass
    
    def requestListFiles(self, req):
        """ The remote peer sent a 'list-files' request. """
        if (isinstance(req.params, Mapping)
            and "register" in req.params and req.params["register"] is True):
            self.remoteNotifications = True
        return self.fileTable.listFiles()
    
    def requestCreateTransfer(self, req):
        """ The remote peer sent a 'create-transfer' request. """
        file = self.fileTable[req.params.get("fileID")]
        transferID = self.transferTable.newTransferID()
        transfer = self.transferTable.createTransfer(transferID, UPLOAD)
        transfer.fileID = file.ID
        transfer.state = "inactive"
        file.transfer = transfer
        self.filesUpdated()
        return transfer
    
    def requestStartTransfer(self, req):
        """ The remote peer sent a 'start-transfer' request. """
        transfer = self.transferTable.find(req.params.get("transferID"), UPLOAD)
        transfer.state = "starting"
        self.filesUpdated()
        self.sendNotification(NOT_TRANSFER_STATE_CHANGED, transfer)
    
    def requestCloseTransfer(self, req):
        """ The remote peer sent a 'close-transfer' request. """
        transfer = self.transferTable.find(req.params.get("transferID"), UPLOAD)
        transfer.state = "closed"
        self.filesUpdated()
        self.sendNotification(NOT_TRANSFER_STATE_CHANGED, transfer)
    
    def notificationFileAdded(self, n):
        """ The remote peer sent a 'file-added' notification. """
        if isinstance(n.params, Mapping):
            self.fileTable.updateFile(n.params, False)
    
    def notificationFileRemoved(self, n):
        """ The remote peer sent a 'file-removed' notification. """
        if isinstance(n.params, Mapping) and "ID" in n.params:
            self.fileTable.removeFile(n.params["ID"], False)

    def notificationTransferStateChanged(self, n):
        """ The remote peer sent a 'transfer-state-changed' notification. """
        transferID = n.params.get("transferID")
        transferState = n.params.get("transferState")
        transfer = self.transferTable.find(transferID, DOWNLOAD)
        transfer.state = transferState
        self.filesUpdated()