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
from spark.async import *
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
        state.reqID = None
        state.transferID = None
        state.direction = None
        state.transferState = None
        state.file = None
        state.started = None
        state.ended = None
    
    def initPatterns(self, loop, state):
        """ Initialize the patterns used by the message loop. """
        super(Transfer, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("init-transfer", int, int, None, int, int),
            Command("start-transfer"),
            Event("file-opened", basestring))
    
    def cleanup(self, state):
        try:
            super(Transfer, self).cleanup(state)
        finally:
            self._changeTransferState(state, "closed")
    
    def _changeTransferState(self, state, transferState):
        if state.transferState != transferState:
            state.transferState = transferState
            self.stateChanged(state.transferID, state.direction, transferState)
    
    def doInitTransfer(self, m, transferID, direction, file, reqID, sessionPid, state):
        state.transferID = transferID
        state.direction = direction
        state.file = file
        state.reqID = reqID
        state.sessionPid = sessionPid
        if state.direction == UPLOAD:
            state.filePath = file.path
        elif state.direction == DOWNLOAD:
            receiveDir = os.path.join(os.path.expanduser("~"), "Desktop")
            state.filePath = os.path.join(receiveDir, file.name)
        state.file = File()
        state.file.start_linked()
        state.file.open(state.filePath)
    
    def onFileOpened(self, m, path, state):
        Process.send(sessionPid, Event("transfer-created",
            state.transferID, state.direction, state.file.ID, state.reqID))
        self._changeTransferState(state, "inactive")
    
    def doStartTransfer(self, m, state):
        state.started = datetime.now()
        self._changeTransferState(state, "active")
    
    def _sendFile(self, state):
        blockSize = 1024
        blockCount = int(math.ceil(float(state.file.size) / blockSize))
    
    def _receiveFile(self, state):
        pass