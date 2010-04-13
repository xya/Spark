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

import types
from datetime import datetime, timedelta
from collections import Mapping
from spark.async import *

__all__ = ["TransferInfo", "TransferTable", "Transfer", "UPLOAD", "DOWNLOAD"]

UPLOAD = 0        # a local file is being sent
DOWNLOAD = 1      # a remote file is being received

class TransferInfo(object):
    """ Provides information about a file transfer. """
    def __init__(self, transferID, direction, fileID, pid):
        self.transferID = transferID
        self.direction = direction
        self.fileID = fileID
        self.pid = pid
        self.state = "created"
        self.completedSize = 0
        self.transferSpeed = 0
        self.started = None
        self.ended = None
    
    def __getstate__(self):
        """ Return the object's state. Used for serialization. """
        return {"transferID": self.transferID, "fileID": self.fileID, "state": self.state}
    
    @property
    def duration(self):
        """ Return the duration of the transfer, or None if the transfer has never been started. """
        if self.started is None:
            return None
        elif self.ended is None:
            return datetime.now - self.started
        else:
            return self.ended - self.started
    
    @property
    def averageSpeed(self):
        """ Return the average transfer speed, in bytes/s. """
        duration = self.duration
        if duration is None:
            return None
        else:
            seconds = duration.seconds
            seconds += (duration.microseconds * 10e-6)
            seconds += (duration.days * 24 * 3600)
            return self.completedSize / seconds
    
    @property
    def progress(self):
        """ Return a number between 0.0 and 1.0 indicating the progress of the transfer. """
        return None
    
    @property
    def eta(self):
        """ Return an estimation of the time when the transfer will be completed. """
        raise NotImplementedError()

class TransferTable(object):
    def __init__(self):
        self.entries = {}
    
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
        state.fileID = None
        state.path = None
        state.transferState = None
    
    def initPatterns(self, loop, state):
        """ Initialize the patterns used by the message loop. """
        super(Transfer, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("init-transfer", int, int, basestring, basestring, int, int))
    
    def cleanup(self, state):
        try:
            super(Transfer, self).cleanup(state)
        finally:
            self._changeTransferState(state, "closed")
    
    def _changeTransferState(self, state, transferState):
        if state.transferState != transferState:
            state.transferState = transferState
            self.stateChanged(state.transferID, state.direction, transferState)
    
    def doInitTransfer(self, m, transferID, direction, fileID, path, reqID, sessionPid, state):
        state.transferID = transferID
        state.direction = direction
        state.fileID = fileID
        state.path = path
        state.sessionPid = sessionPid
        Process.send(sessionPid, Event("transfer-created", transferID, direction, fileID, reqID))
        self._changeTransferState(state, "inactive")