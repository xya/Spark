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

import math
from datetime import datetime, timedelta
from spark.async import *

__all__ = ["Transfer"]
class Transfer(ProcessBase):
    def __init__(self):
        super(Transfer, self).__init__()
        self.stateChanged = EventSender("transfer-state-changed", int, int, basestring)
    
    def initState(self, state):
        """ Initialize the process state. """
        super(Transfer, self).initState(state)
        state.sessionPid = None
        state.transferID = None
        state.direction = None
        state.transferState = None
        state.file = None
        state.started = None
    
    def initPatterns(self, loop, state):
        """ Initialize the patterns used by the message loop. """
        super(Transfer, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("init-transfer", int, int, None, int, int),
            Command("start-transfer"))
    
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
        state.sessionPid = sessionPid
        Process.send(sessionPid, Event("transfer-created", transferID, direction, file.ID, reqID))
        self._changeTransferState(state, "inactive")
    
    def doStartTransfer(self, m, state):
        blockSize = 1024
        blockCount = int(math.ceil(float(state.file.size) / blockSize))
        self._changeTransferState(state, "active")
        state.started = datetime.now()