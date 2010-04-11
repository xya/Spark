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
import functools
import types
from spark.async import Delegate, Process, ProcessRunner
from spark.messaging import *

__all__ = ["SparkApplication", "Session"]

class SparkApplication(object):
    """ Hold the state of the whole application. """
    def __init__(self):
        self._myIPaddress = "127.0.0.1"
        self._isConnected = False
        self._activeTransfers = 0
        self._uploadSpeed = 0.0
        self._downloadSpeed = 0.0
        self.session = Session()
        self.runner = ProcessRunner(self.session)
        self.runner.start()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, val, tb):
        try:
            self.runner.stop()
        except Exception:
            logging.exception("Error while stoping the session")
    
    def connect(self, address):
        Process.send(self.runner.pid, ("connect", address))
    
    def bind(self, address):
        Process.send(self.runner.pid, ("bind", address))
    
    def disconnect(self):
        Process.send(self.runner.pid, ("disconnect", ))
    
    @property
    def myIPaddress(self):
        """ Return the public IP address of the user, if known. """
        return self._myIPaddress
    
    @property
    def isConnected(self):
        """ Determine whether the session is active, i.e. we are connected to a remote peer. """
        return self._isConnected
    
    @property
    def activeTransfers(self):
        """ Return the number of active transfers. """
        return self._activeTransfers
    
    @property
    def uploadSpeed(self):
        """ Return the total upload speed, across all active transfers. """
        return self._uploadSpeed
    
    @property
    def downloadSpeed(self):
        """ Return the total download speed, across all active transfers. """
        return self._downloadSpeed
    
    def updateState(self, sessionState):
        """ Update the application state. """
        self._isConnected = sessionState["isConnected"]
        self._activeTransfers = sessionState["activeTransfers"]
        self._uploadSpeed = sessionState["uploadSpeed"]
        self._downloadSpeed = sessionState["downloadSpeed"]
    
    Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
    def formatSize(self, size):
        for unit, count in reversed(SparkApplication.Units):
            if size >= count:
                return "%0.2f %s" % (size / float(count), unit)
        return "%d byte" % size

_fileShareMethods = ["files", "addFile", "removeFile", "startTransfer", "stopTransfer"]

class Session(Service):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self):
        super(Session, self).__init__()
        self.stateChanged = NotificationEvent("session-state-changed")
        self.filesUpdated = NotificationEvent("files-updated")
        
    def initState(self, loop, state):
        super(Session, self).initState(loop, state)
        state.isConnected = False
        
    def initPatterns(self, loop, state):
        super(Session, self).initPatterns(loop, state)
        loop.addPattern(Request("update-session-state"), self.updateSessionState)
        
    def onProtocolNegociated(self, m, state):
        super(Session, self).onProtocolNegociated(m, state)
        state.isConnected = True
        self.updateSessionState(m, state)
    
    def onDisconnected(self, m, state):
        super(Session, self).onDisconnected(m, state)
        state.isConnected = False
        self.updateSessionState(m, state)
    
    def updateSessionState(self, m, state):
        self.stateChanged({"isConnected" : state.isConnected,
            "activeTransfers" : 0, "uploadSpeed" : 0.0, "downloadSpeed" : 0.0})