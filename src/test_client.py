#!/usr/bin/env python
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

import signal
import os
import time
import thread
import logging
from functools import partial
from spark.async import *
from spark.messaging import *
from spark.fileshare import *

SERVER_ADDRESS = "127.0.0.1"
SERVER_PORT = 4559

class MainProcess(ProcessBase):
    def initState(self, state):
        super(MainProcess, self).initState(state)
        state.startedTransfer = False
        state.app = SparkApplication()
        state.app.connected += partial(self._connected, state)
        state.app.connectionError += partial(self._connectionError, state)
        state.app.disconnected += partial(self._disconnected, state)
        state.app.filesUpdated += partial(self._filesUpdated, state)
        state.app.transferUpdated += partial(self._transferUpdated, state)
        state.app.start_linked()
    
    def initPatterns(self, matcher, state):
        super(MainProcess, self).initPatterns(matcher, state)
        state.app.installHandlers(matcher)
    
    def cleanup(self, state):
        try:
            state.app.session.stop()
        finally:
            super(MainProcess, self).cleanup(state)
            # signal the main thread that MainProcess exited
            thread.interrupt_main()
    
    def onStart(self, state):
        state.app.connect((SERVER_ADDRESS, SERVER_PORT))
    
    def _connected(self, state):
        pass
    
    def _connectionError(self, state, e):
        raise ProcessExit(("connection-error", e))
    
    def _filesUpdated(self, state):
        if not state.startedTransfer:
            for fileID in state.app.files:
                state.startedTransfer = True
                state.app.startTransfer(fileID)
                return
    
    def _transferUpdated(self, state, fileID):
        if state.startedTransfer:
            file = state.app.files[fileID]
            if file and file.transfer and file.transfer.state == "closed":
                state.app.disconnect()

    def _disconnected(self, state):
        raise ProcessExit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main = MainProcess()
    main.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pid = main.pid
        if pid is not None:
            Process.kill(pid, False)