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
from functools import partial
from spark.async import *
from spark.messaging import *
from spark.fileshare import SharedFile, FileTable, LOCAL, REMOTE
from spark.fileshare import TransferTable, UPLOAD, DOWNLOAD

__all__ = ["FileSharingSession"]

class FileSharingSession(Service):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self):
        super(FileSharingSession, self).__init__()
        self.stateChanged = EventSender("session-state-changed", dict)
        self.filesUpdated = EventSender("files-updated")
        
    def initState(self, state):
        super(FileSharingSession, self).initState(state)
        state.remoteNotifications = False
        state.fileTable = FileTable()
        state.fileTable.fileAdded += partial(self.cacheFileAdded, state)
        state.fileTable.fileUpdated += partial(self.cacheFileUpdated, state)
        state.fileTable.fileRemoved += partial(self.cacheFileRemoved, state)
        state.transferTable = TransferTable()
    
    def initPatterns(self, loop, state):
        super(FileSharingSession, self).initPatterns(loop, state)
        loop.addHandlers(self,
            # internal commands
            Command("update-session-state"),
            Command("list-files", bool, int),
            Command("add-file", basestring, int),
            Command("remove-file", basestring, int),
            Command("start-transfer", int, int),
            Command("stop-transfer", int, int),
            # messages from the remote peer
            Request("list-files", bool),
            Response("list-files", None),
            Request("create-transfer", basestring),
            Response("create-transfer", int, basestring),
            Request("start-transfer", int),
            Response("start-transfer"),
            Request("close-transfer", int),
            Response("close-transfer"),
            Notification("file-added", None),
            Notification("file-removed", basestring),
            Notification("transfer-state-changed", int, basestring)
        )
    
    def cleanup(self, state):
        try:
            super(FileSharingSession, self).cleanup(state)
        finally:
            pass    # TODO: perform session cleanup here
    
    def sessionStarted(self, state):
        self.sendRequest(state, "list-files", True)
    
    def sessionEnded(self, state):
        pass
    
    def doUpdateSessionState(self, m, state):
        self.stateChanged({"activeTransfers" : 0,
            "uploadSpeed" : 0.0, "downloadSpeed" : 0.0})

    def doListFiles(self, m, excludeRemoved, senderPid, state):
        """ Return a copy of the current file table, which maps file IDs to files. """
        cache = state.fileTable.files
        if excludeRemoved:
            files = {}
            for fileID, file in cache.items():
                # exclude local files that have been removed by the user
                if (file.origin == REMOTE) or file.localCopy:
                    files[fileID] = file
        else:
            files = cache.copy()
        Process.send(senderPid, Event("list-files", files))
    
    def responseListFiles(self, m, transID, files, state):
        state.fileTable.updateTable(files, REMOTE)
        
    def doAddFile(self, m, path, senderPid, state):
        """ Add the local file with the given path to the list. """
        state.fileTable.addFile(path)
    
    def doRemoveFile(self, m, fileID, senderPid, state):
        """ Remove the file (local or remote) with the given ID from the list. """
        state.fileTable.removeFile(fileID, True)
    
    def doStartTransfer(self, m, fileID, senderPid, state):
        """ Start receiving the remote file with the given ID. """
        file = state.fileTable[fileID]
        if file.transfer is None:
            self.sendRequest(state, "create-transfer", fileID)
    
    def responseCreateTransfer(self, m, transID, transferID, fileID, state):
        file = state.fileTable[fileID]
        transfer = state.transferTable.createTransfer(transferID, DOWNLOAD)
        transfer.fileID = file.ID
        file.transfer = transfer
        self.filesUpdated()
        self.sendRequest(state, "start-transfer", transferID)
    
    def doStopTransfer(self, m, fileID, state):
        """ Stop receiving the remote file with the given ID. """
        raise NotImplementedError()
    
    def cacheFileAdded(self, state, fileID, origin):
        self.filesUpdated()
        if (origin == LOCAL) and state.remoteNotifications and state.isConnected:
            file = state.fileTable[fileID]
            self.sendNotification(state, "file-added", file)
    
    def cacheFileUpdated(self, state, fileID, origin):
        self.filesUpdated()
    
    def cacheFileRemoved(self, state, fileID, origin):
        self.filesUpdated()
        if (origin == LOCAL) and state.remoteNotifications and state.isConnected:
            self.sendNotification(state, "file-removed", fileID)
    
    def requestListFiles(self, m, transID, register, state):
        """ The remote peer sent a 'list-files' request. """
        if register is True:
            state.remoteNotifications = True
        files = state.fileTable.files.copy()
        self.sendResponse(state, m, files)
    
    def requestCreateTransfer(self, m, transID, fileID, state):
        """ The remote peer sent a 'create-transfer' request. """
        file = self.fileTable[fileID]
        transferID = self.transferTable.newTransferID()
        transfer = self.transferTable.createTransfer(transferID, UPLOAD)
        transfer.fileID = file.ID
        transfer.state = "inactive"
        file.transfer = transfer
        self.filesUpdated()
        self.sendResponse(state, m, transferID)
        self.sendNotification("transfer-state-changed", transferID, transfer.state)
    
    def requestStartTransfer(self, m, transID, transferID, state):
        """ The remote peer sent a 'start-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        transfer.state = "starting"
        self.filesUpdated()
        self.sendResponse(state, m)
        self.sendNotification("transfer-state-changed", transferID, transfer.state)
    
    def requestCloseTransfer(self, m, transID, transferID, state):
        """ The remote peer sent a 'close-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        transfer.state = "closed"
        self.filesUpdated()
        self.sendResponse(state, m)
        self.sendNotification("transfer-state-changed", transferID, transfer.state)
    
    def notificationFileAdded(self, m, transID, fileInfo, state):
        """ The remote peer sent a 'file-added' notification. """
        state.fileTable.updateFile(fileInfo, REMOTE)
    
    def notificationFileRemoved(self, m, transID, fileID, state):
        """ The remote peer sent a 'file-removed' notification. """
        state.fileTable.removeFile(fileID, REMOTE)
    
    def notificationTransferStateChanged(self, m, transID, transferID, transferState, state):
        """ The remote peer sent a 'transfer-state-changed' notification. """
        transfer = state.transferTable.find(transferID, DOWNLOAD)
        transfer.state = transferState
        self.filesUpdated()