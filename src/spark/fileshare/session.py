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

from collections import Mapping
from functools import partial
from spark.core import *
from spark.messaging import *
from spark.fileshare.tables import *
from spark.fileshare.transfers import *

__all__ = ["FileSharingSession"]

class FileSharingSession(Service):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self):
        super(FileSharingSession, self).__init__()
        self.stateChanged = EventSender("session-state-changed", dict)
        self.fileListUpdated = EventSender("file-list-updated")
        self.fileUpdated = EventSender("file-updated", SharedFile)
        self.ended = EventSender("ended")
    
    def initState(self, state):
        super(FileSharingSession, self).initState(state)
        state.remoteNotifications = False
        state.fileTable = FileTable()
        state.fileTable.fileAdded += partial(self.cacheFileAdded, state)
        state.fileTable.fileUpdated += partial(self.cacheFileUpdated, state)
        state.fileTable.fileRemoved += partial(self.cacheFileRemoved, state)
        state.transferTable = TransferTable()
        state.pendingTransferReqs = {}
        state.activeTransfers = 0
    
    def initPatterns(self, loop, state):
        super(FileSharingSession, self).initPatterns(loop, state)
        loop.addHandlers(self,
            # internal messages
            Command("update-session-state"),
            Command("update-transfer-info"),
            Command("list-files", bool, int),
            Command("add-file", basestring, int),
            Command("remove-file", basestring, int),
            Command("start-transfer", basestring, int),
            Command("stop-transfer", basestring, int),
            Event("transfer-created", int, int),
            Event("transfer-state-changed", int, int, basestring),
            Event("transfer-info-updated", int, int, TransferInfo),
            # messages from the remote peer
            Request("list-files", bool),
            Response("list-files", None),
            Request("create-transfer", basestring),
            Response("create-transfer", basestring, int),
            Request("start-transfer", int),
            Request("close-transfer", int),
            Notification("file-added", None),
            Notification("file-removed", basestring),
            Notification("transfer-state-changed", int, basestring))
        loop.addPattern(Block, self._blockReceived)
    
    def cleanup(self, state):
        try:
            self._stopTransfers(state)
            self.ended()
        finally:
            super(FileSharingSession, self).cleanup(state)
    
    def sessionStarted(self, state):
        self.sendRequest(state, "list-files", True)
    
    def sessionEnded(self, state):
        self._stopTransfers(state)
    
    def doUpdateSessionState(self, m, state):
        self._updateSessionState(state, force=True)
    
    def _updateSessionState(self, state, force=False):
        activeTransfers = 0
        for transfer in state.transferTable:
            if transfer.state == "active":
                activeTransfers += 1
        if force or state.activeTransfers != activeTransfers:
            state.activeTransfers = activeTransfers
            self.stateChanged({"activeTransfers" : state.activeTransfers,
                "uploadSpeed" : 0.0, "downloadSpeed" : 0.0})
    
    def doListFiles(self, m, excludeRemoved, senderPid, state):
        """ Return a copy of the current file table, which maps file IDs to files. """
        cache = state.fileTable.files
        files = {}
        for fileID, file in cache.items():
            # exclude local files that have been removed by the user
            if not excludeRemoved or (file.origin == REMOTE) or file.hasCopy(LOCAL):
                files[fileID] = file.copy(includeTransfer=False)
        Process.send(senderPid, Event("list-files", files))
    
    def requestListFiles(self, m, transID, register, state):
        """ The remote peer sent a 'list-files' request. """
        if register is True:
            state.remoteNotifications = True
        files = state.fileTable.files.copy()
        self.sendResponse(state, m, files)
    
    def responseListFiles(self, m, transID, files, state):
        state.fileTable.updateTable(files, REMOTE)
    
    def cacheFileUpdated(self, state, fileID, origin):
        self.fileUpdated(state.fileTable[fileID].copy())
    
    def doAddFile(self, m, path, senderPid, state):
        """ Add the local file with the given path to the list. """
        state.fileTable.addFile(path)
    
    def cacheFileAdded(self, state, fileID, origin):
        state.logger.info("Added file %s.", repr((fileID, origin)))
        self.fileListUpdated()
        if (origin == LOCAL) and state.remoteNotifications and state.isConnected:
            file = state.fileTable[fileID]
            self.sendNotification(state, "file-added", file)
    
    def notificationFileAdded(self, m, transID, fileInfo, state):
        """ The remote peer sent a 'file-added' notification. """
        state.fileTable.updateFile(fileInfo, REMOTE)
    
    def doRemoveFile(self, m, fileID, senderPid, state):
        """ Remove the file (local or remote) with the given ID from the list. """
        state.fileTable.removeFile(fileID, True)
    
    def cacheFileRemoved(self, state, fileID, origin):
        state.logger.info("Removed file %s.", repr((fileID, origin)))
        self.fileListUpdated()
        if (origin == LOCAL) and state.remoteNotifications and state.isConnected:
            self.sendNotification(state, "file-removed", fileID)
    
    def notificationFileRemoved(self, m, transID, fileID, state):
        """ The remote peer sent a 'file-removed' notification. """
        state.fileTable.removeFile(fileID, REMOTE)
    
    def doStartTransfer(self, m, fileID, senderPid, state):
        """ Start receiving the remote file with the given ID. """
        file = state.fileTable[fileID]
        if file.transfer is None:
            self.sendRequest(state, "create-transfer", fileID)
    
    def requestCreateTransfer(self, m, transID, fileID, state):
        """ The remote peer sent a 'create-transfer' request. """
        file = state.fileTable[fileID]
        if file and (file.origin == LOCAL):
            transferID = self._createTransferProcess(None, Upload, file, state)
            state.pendingTransferReqs[transferID] = (transID, fileID)
        else:
            state.messenger.send(Response("create-transfer-error", fileID).withID(transID))
    
    def responseCreateTransfer(self, m, transID, fileID, transferID, state):
        file = state.fileTable[fileID]
        if file and (file.origin == REMOTE):
            self._createTransferProcess(transferID, Download, file, state)
    
    def _createTransferProcess(self, transferID, factory, file, state):
        direction = factory.direction
        # either create an instance of class Upload or Download
        process = factory()
        process.start_linked()
        if not transferID:
            transferID = process.pid
        process.stateChanged.suscribe()
        if direction == DOWNLOAD:
            state.messenger.addRecipient(Block(transferID), process.pid)
        Process.send(process.pid, Command("init-transfer", transferID, direction, file, self.pid))
        transfer = state.transferTable.createTransfer(transferID, direction, file.ID, process.pid)
        file.transfer = transfer
        return transferID
    
    def onTransferCreated(self, m, transferID, direction, state):
        if direction == UPLOAD:
            reqID, fileID = state.pendingTransferReqs[transferID]
            del state.pendingTransferReqs[transferID]
            resp = Response("create-transfer", fileID, transferID).withID(reqID)
            state.messenger.send(resp)
        elif direction == DOWNLOAD:
            self.sendRequest(state, "start-transfer", transferID)
    
    def requestStartTransfer(self, m, transID, transferID, state):
        """ The remote peer sent a 'start-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        if transfer:
            Process.send(transfer.pid, Command("start-upload", state.messenger.pid))
    
    def _blockReceived(self, b, state):
         transfer = state.transferTable.find(b.transferID, DOWNLOAD)
         if transfer:
            Process.send(transfer.pid, b)
    
    def doStopTransfer(self, m, fileID, state):
        """ Stop receiving the remote file with the given ID. """
        file = state.fileTable[fileID]
        if file and file.transfer:
            Process.send(transfer.pid, Command("close-transfer"))
    
    def _stopTransfers(self, state):
        state.transferTable.clear()
        state.fileTable.clearTransfers()
    
    def requestCloseTransfer(self, m, transID, transferID, state):
        """ The remote peer sent a 'close-transfer' request. """
        transfer = state.transferTable.find(transferID, UPLOAD)
        if transfer:
            Process.send(transfer.pid, Command("close-transfer"))
    
    def onTransferStateChanged(self, m, transferID, direction, transferState, state):
        # TODO: remove this event, use only transfer-info-updated?
        transfer = state.transferTable.find(transferID, direction)
        if transfer:
            transfer.state = transferState
            if (direction == UPLOAD) and state.isConnected:
                self.sendNotification(state, "transfer-state-changed", transferID, transferState)
            if (direction == DOWNLOAD) and (transferState == "finished"):
                self.sendRequest(state, "close-transfer", transferID)
            self._updateSessionState(state)
            Process.try_send(transfer.pid, Command("transfer-info"))
    
    def notificationTransferStateChanged(self, m, transID, transferID, transferState, state):
        """ The remote peer sent a 'transfer-state-changed' notification. """
        transfer = state.transferTable.find(transferID, DOWNLOAD)
        if transfer:
            Process.send(transfer.pid, Event("remote-state-changed", transferState))
    
    def onTransferInfoUpdated(self, m, transferID, direction, transfer, state):
        cached = state.transferTable.find(transferID, direction)
        if cached:
            cached.updateState(transfer)
            file = state.fileTable[transfer.fileID]
            if direction == UPLOAD:
                file.remoteCopySize = transfer.completedSize
            elif direction == DOWNLOAD:
                file.localCopySize = transfer.completedSize
            self.fileUpdated(file)
    
    def doUpdateTransferInfo(self, m, state):
        for transfer in state.transferTable:
            Process.try_send(transfer.pid, Command("transfer-info"))