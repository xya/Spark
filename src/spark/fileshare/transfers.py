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
import math
from datetime import datetime, timedelta
from collections import defaultdict
from spark.async import *
from spark.messaging import *
from spark.fileshare.tables import *

__all__ = ["Transfer"]
class Transfer(ProcessBase):
    def __init__(self):
        super(Transfer, self).__init__()
        self.stateChanged = EventSender("transfer-state-changed", int, int, basestring)
    
    def initState(self, state):
        """ Initialize the process state. """
        super(Transfer, self).initState(state)
        state.sessionPid = None
        state.messengerPid = None
        state.transferID = None
        state.direction = None
        state.transferState = None
        state.file = None
        state.path = None
        state.stream = None
        state.blockTable = None
        state.offset = None
        state.started = None
        state.ended = None
    
    def initPatterns(self, loop, state):
        """ Initialize the patterns used by the message loop. """
        super(Transfer, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("init-transfer", int, int, None, int, int),
            Command("start-transfer"),
            Command("close-transfer"),
            Command("transfer-info"),
            Event("remote-state-changed", basestring),
            Event("block-received", Block()))
    
    def cleanup(self, state):
        try:
            self._closeFile(state)
            self._changeTransferState(state, "closed")
        finally:
            super(Transfer, self).cleanup(state)
    
    def _closeFile(self, state):
        if state.stream:
            state.stream.close()
            state.stream = None
            state.logger.info("Closed file '%s'.", state.path) 
    
    def _changeTransferState(self, state, transferState):
        if state.transferState != transferState:
            state.logger.info("Transfer state changed from '%s' to '%s'.",
                state.transferState, transferState)
            state.transferState = transferState
            self.stateChanged(state.transferID, state.direction, transferState)
            self._sendTransferInfo(state)
    
    def onRemoteStateChanged(self, m, transferState, state):
        self._changeTransferState(state, transferState)
        if transferState == "active":
            self._startTransfer(state)
        elif transferState == "closed":
            self._closeTransfer(state)
    
    def doInitTransfer(self, m, transferID, direction, file, sessionPid, messengerPid, state):
        state.logger.info("Initializing transfer for file %s.", repr((file.ID, direction)))
        state.transferID = transferID
        state.direction = direction
        state.file = file
        state.sessionPid = sessionPid
        state.messengerPid = messengerPid
        state.blockSize = 1024
        state.receivedBlocks = 0
        state.completedSize = 0
        state.totalBlocks = int(math.ceil(float(file.size) / state.blockSize))
        if state.direction == UPLOAD:
            state.path = file.path
            state.stream = open(state.path, "rb")
            state.nextBlock = 0
        elif state.direction == DOWNLOAD:
            state.blockTable = defaultdict(bool)
            receiveDir = os.path.join(os.path.expanduser("~"), "Desktop")
            state.path = os.path.join(receiveDir, file.name)
            state.stream = open(state.path, "wb")
        state.logger.info("Opened file '%s'.", state.path)
        state.offset = 0
        state.transferState = "created"
        Process.send(sessionPid, Event("transfer-created", state.transferID, state.direction))
        self._changeTransferState(state, "inactive")
    
    def doStartTransfer(self, m, state):
        self._startTransfer(state)
    
    def _startTransfer(self, state):
        state.logger.info("Starting transfer.")
        state.started = datetime.now()
        if state.direction == UPLOAD:
            self._changeTransferState(state, "active")
            self._sendFile(state)
    
    def _sendFile(self, state):
        while state.transferState == "active":
            # we have to keep checking the process' message queue while sending blocks
            # otherwise the process will be unresponsive (can't pause or cancel)
            ok, m = Process.try_receive()
            if ok:
                self.handleMessage(m, state)
            else:
                self._sendBlock(state)
    
    def _sendBlock(self, state):
        if state.nextBlock >= state.totalBlocks:
            self._transferComplete(state)
        else:
            # read the block
            blockData = state.stream.read(state.blockSize)
            state.offset += len(blockData)
            block = Block(state.transferID, state.nextBlock, blockData)
            state.nextBlock += 1
            state.completedSize += len(blockData)
            # send it
            Process.send(state.messengerPid, Command("send", block, self.pid))
    
    def onBlockReceived(self, m, b, state):
        blockID = b.blockID
        if (not state.blockTable[blockID]) and (blockID < state.totalBlocks):
            fileOffset = blockID * state.blockSize
            if state.offset != fileOffset:
                state.stream.seek(fileOffset)
            state.stream.write(b.blockData)
            state.offset += len(b.blockData)
            state.blockTable[blockID] = True
            state.receivedBlocks += 1
            state.completedSize += len(b.blockData)
        if state.receivedBlocks == state.totalBlocks:
            self._transferComplete(state)
    
    def _transferComplete(self, state):
        state.ended = datetime.now()
        self._changeTransferState(state, "finished")
        state.logger.info("Transfer complete.")
        info = self._transferInfo(state)
        state.logger.info("Transfered %s in %s (%s/s).",
            formatSize(info.completedSize),
            info.duration,
            formatSize(info.averageSpeed))
    
    def doTransferInfo(self, m, state):
        """ Send current transfer information to the process. """
        self._sendTransferInfo(state)
    
    def _sendTransferInfo(self, state):
        info = self._transferInfo(state)
        Process.try_send(state.sessionPid, Event("transfer-info-updated",
            state.transferID, state.direction, info))
    
    def _transferInfo(self, state):
        info = TransferInfo(state.transferID, state.direction, state.file.ID, self.pid)
        info.started = state.started
        info.ended = state.ended
        info.state = state.transferState
        info.completedSize = state.completedSize
        info.originalSize = state.file.size
        return info
    
    def doCloseTransfer(self, m, state):
        self._closeTransfer(state)
    
    def _closeTransfer(self, state):
        state.logger.info("Closing transfer.")
        self._closeFile(state)
        raise ProcessExit()