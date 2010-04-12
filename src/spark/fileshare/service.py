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
from spark.fileshare import SharedFile, FileTable, TransferTable, UPLOAD, DOWNLOAD

__all__ = ["FileShare"]

class FileShare(Service):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self):
        super(FileShare, self).__init__()
        self.stateChanged = EventSender("session-state-changed", dict)
        self.filesUpdated = EventSender("files-updated")
        
    def initState(self, loop, state):
        super(FileShare, self).initState(loop, state)
        state.isConnected = False
        state.remoteNotifications = False
        state.fileTable = FileTable()
        state.fileTable.fileAdded += partial(self.cacheFileAdded, state)
        state.fileTable.fileUpdated += partial(self.cacheFileUpdated, state)
        state.fileTable.fileRemoved += partial(self.cacheFileRemoved, state)
        state.transferTable = TransferTable()
    
    def initPatterns(self, loop, state):
        super(FileShare, self).initPatterns(loop, state)
        # internal commands
        loop.addPattern(Command("update-session-state"), self.updateSessionState)
        loop.addPattern(Command("list-files", bool, int), self.commandListFiles)
        loop.addPattern(Command("add-file", basestring, int), self.commandAddFile)
        loop.addPattern(Command("remove-file", int, int), self.commandRemoveFile)
        loop.addPattern(Command("start-transfer", int, int), self.commandStartTransfer)
        loop.addPattern(Command("stop-transfer", int, int), self.commandStopTransfer)
        # messages from the remote peer
        loop.addPattern(Response("list-files", None), self.responseListFiles)
        loop.addPattern(Response("create-transfer", int, basestring), self.responseCreateTransfer)
        loop.addPattern(Notification("file-added", None), self.notificationFileAdded)
        loop.addPattern(Notification("file-removed", basestring), self.notificationFileRemoved)
        loop.addPattern(Notification("transfer-state-changed", int, basestring), self.notificationTransferStateChanged)
    
    def onProtocolNegociated(self, m, state):
        super(FileShare, self).onProtocolNegociated(m, state)
        state.isConnected = True
        self.updateSessionState(m, state)
        self.sendRequest(state, "list-files", True)
    
    def onDisconnected(self, m, state):
        super(FileShare, self).onDisconnected(m, state)
        state.isConnected = False
        self.updateSessionState(m, state)
    
    def updateSessionState(self, m, state):
        self.stateChanged({"isConnected" : state.isConnected,
            "activeTransfers" : 0, "uploadSpeed" : 0.0, "downloadSpeed" : 0.0})

    def commandListFiles(self, m, state):
        """ Return a copy of the current file table, which maps file IDs to files. """
        excludeRemoved, senderPid = m[2:4]
        cache = state.fileTable.listFiles()
        if excludeRemoved:
            files = {}
            for fileID, file in cache.items():
                if not file.localRemoved:
                    files[fileID] = file
        else:
            files = cache.copy()
        Process.send(senderPid, Event("list-files", files))
    
    def responseListFiles(self, m, state):
        files = m[3]
        state.fileTable.updateTable(files, False)
        
    def commandAddFile(self, m, state):
        """ Add the local file with the given path to the list. """
        path, senderPid = m[2:4]
        state.fileTable.addFile(path)
    
    def commandRemoveFile(self, m, state):
        """ Remove the file (local or remote) with the given ID from the list. """
        fileID, senderPid = m[2:4]
        state.fileTable.removeFile(fileID, True)
    
    def commandStartTransfer(self, m, state):
        """ Start receiving the remote file with the given ID. """
        fileID, senderPid = m[2:4]
        file = state.fileTable[fileID]
        if file.transfer is None:
            self.sendRequest(state, "create-transfer", fileID)
    
    def responseCreateTransfer(self, m, state):
        transferID, fileID = m[2:4]
        file = state.fileTable[fileID]
        transfer = state.transferTable.createTransfer(transferID, DOWNLOAD)
        transfer.fileID = file.ID
        file.transfer = transfer
        self.filesUpdated()
        self.sendRequest(state, "start-transfer", transferID)
    
    def commandStopTransfer(self, fileID):
        """ Stop receiving the remote file with the given ID. """
        raise NotImplementedError()
    
    def cacheFileAdded(self, state, fileID, local):
        self.filesUpdated()
        if local and state.remoteNotifications and state.isConnected:
            file = state.fileTable[fileID]
            self.sendNotification(state, "file-added", file)
    
    def cacheFileUpdated(self, state, fileID, local):
        self.filesUpdated()
    
    def cacheFileRemoved(self, state, fileID, local):
        self.filesUpdated()
        if local and state.remoteNotifications and state.isConnected:
            self.sendNotification(state, "file-removed", fileID)
    
    def requestListFiles(self, m, register, state):
        """ The remote peer sent a 'list-files' request. """
        if register is True:
            state.remoteNotifications = True
        files = state.fileTable.listFiles() #TODO: only local
        self.sendResponse(state, m, files)
    
    def requestCreateTransfer(self, m, fileID, state):
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
    
    def requestStartTransfer(self, m, transferID, state):
        """ The remote peer sent a 'start-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        transfer.state = "starting"
        self.filesUpdated()
        self.sendResponse(state, m)
        self.sendNotification("transfer-state-changed", transferID, transfer.state)
    
    def requestCloseTransfer(self, m, transferID, state):
        """ The remote peer sent a 'close-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        transfer.state = "closed"
        self.filesUpdated()
        self.sendResponse(state, m)
        self.sendNotification("transfer-state-changed", transferID, transfer.state)
    
    def notificationFileAdded(self, m, state):
        """ The remote peer sent a 'file-added' notification. """
        fileInfo = m[3]
        state.fileTable.updateFile(fileInfo, False)
    
    def notificationFileRemoved(self, m, state):
        """ The remote peer sent a 'file-removed' notification. """
        fileID = m[3]
        state.fileTable.removeFile(fileID, False)
    
    def notificationTransferStateChanged(self, m, state):
        """ The remote peer sent a 'transfer-state-changed' notification. """
        transferID, transferState = m[3:5]
        transfer = state.transferTable.find(transferID, DOWNLOAD)
        transfer.state = transferState
        self.filesUpdated()