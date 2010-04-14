# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Pierre-André Saulais <pasaulais@free.fr>
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

from spark.async.process import *

__all__ = ["File"]

class File(ProcessBase):
    """ Process that can read from and write to files. """
    def __init__(self):
        super(File, self).__init__()
    
    def open(self, path, mode=None, senderPid=None):
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.pid, Command("open-file", path, mode, senderPid))
    
    def initState(self, state):
        super(File, self).initState(loop)
        state.path = None
        state.file = None
        state.offset = None
        state.senderPid = None
        state.logger = Process.logger()
    
    def initPatterns(self, loop, state):
        super(File, self).initPatterns(loop, state)
        loop.addHandlers(self,
            Command("open-file", basestring, basestring, int))
    
    def cleanup(self, state):
        try:
            super(File, self).cleanup(state)
        finally:
            if state.file:
                state.file.close()
                state.file = None
    
    def _close(self, state):
        if state.file:
            state.file.close()
            state.file = None
            state.logger.info("Closed file '%s'.", state.path) 
    
    def doOpen(self, m, path, mode, senderPid, state):
        state.path = path
        state.file = open(path, mode)
        state.offset = 0
        state.logger("Opened file '%s'.", path)
        state.senderPid = senderPid
        Process.send(senderPid, Event("file-opened", path))