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

import logging
from functools import partial
from spark.async import *
from spark.messaging import *
from spark.fileshare import *

BIND_ADDRESS = "127.0.0.1"
BIND_PORT = 4559

class MainProcess(ProcessBase):
    def initState(self, state):
        super(MainProcess, self).initState(state)
        state.app = SparkApplication()
        state.app.connected += partial(self._connected, state)
        state.app.disconnected += partial(self._disconnected, state)
        state.app.start_linked()
    
    def initPatterns(self, matcher, state):
        super(MainProcess, self).initPatterns(matcher, state)
        state.app.installHandlers(matcher)
    
    def cleanup(self, state):
        try:
            state.app.session.stop()
        finally:
            super(MainProcess, self).cleanup(state)
    
    def onStart(self, state):
        state.app.bind((BIND_ADDRESS, BIND_PORT))
    
    def _connected(self, state):
        state.app.addFile("/home/xya/I'm a lagger.mp3")
    
    def _disconnected(self, state):
        raise ProcessExit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main = MainProcess()
    try:
        main.attach()
    except ProcessExit as e:
        if e.reason is not None:
            logging.error("Main process exited with reason %s.", repr(e.reason))