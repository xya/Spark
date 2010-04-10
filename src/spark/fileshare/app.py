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
from spark.async import Delegate, process
from spark.messaging import *
from spark.fileshare import FileShare

__all__ = ["SparkApplication", "Session"]

def sessionMethod(func):
    """ Invoke a callable in the context of the session. """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return self.reactor.send(func, *args, **kwargs)
    return wrapper

class SparkApplication(object):
    """ Hold the state of the whole application. """
    def __init__(self, bindAddr=None):
        self.session = Session(bindAddr)
        self._myIPaddress = "127.0.0.1"
        self._isConnected = False
        self._activeTransfers = 0
        self._uploadSpeed = 0.0
        self._downloadSpeed = 0.0
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, val, tb):
        try:
            self.session.dispose()
        except Exception:
            logging.exception("Error while disposing the session")
    
    def connect(self, address):
        process.send(self.session.pid, ("connect", address))
    
    def listen(self, address):
        process.send(self.session.pid, ("listen", address))
    
    def disconnect(self):
        process.send(self.session.pid, ("disconnect", ))
    
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

class Session(object):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self, bindAddr=None):
        self.connected = NotificationEvent("connected")
        self.connectionError = NotificationEvent("connection-error")
        self.disconnected = NotificationEvent("disconnected")
        self.stateChanged = NotificationEvent("session-state-changed")
        self.filesUpdated = NotificationEvent("files-updated")
        self.pid = process.spawn(self._entry, args=(bindAddr, ), name="Session")
    
    def _entry(self, bindAddr):
        loop = MessageMatcher()
        state = process.ProcessState
        state.isConnected = False
        state.bindAddr = bindAddr
        state.messenger = TcpMessenger()
        # messages received from TcpMessenger
        state.messenger.protocolNegociated.suscribe(matcher=loop, callable=self.onProtocolNegociated)
        state.messenger.disconnected.suscribe(matcher=loop, callable=self.onDisconnected)
        loop.addPattern(("connection-error", None), self.onConnectionError)
        # messages received from the caller
        loop.addPattern(Request("update-session-state"), self.updateSessionState)
        loop.addPattern(("connect", None), self.connectMessenger)
        loop.addPattern(("listen", None), self.listenMessenger)
        loop.addPattern(("accept", ), self.acceptMessenger)
        loop.addPattern(("disconnect", ), self.disconnectMessenger)
        loop.addPattern("close", result=False)
        if state.bindAddr:
            state.messenger.listen(state.bindAddr)
            state.messenger.accept()
        try:
            loop.run(state)
        finally:
            state.messenger.close()
    
    def onConnectionError(self, m, state):
        self.connectionError(m[1])
    
    def onProtocolNegociated(self, m, state):
        state.isConnected = True
        self.connected()
        self.updateSessionState(m, state)
    
    def onDisconnected(self, m, state):
        state.isConnected = False
        self.disconnected()
        self.updateSessionState(m, state)
        if state.bindAddr:
            state.messenger.accept()
    
    def updateSessionState(self, m, state):
        self.stateChanged({"isConnected" : state.isConnected,
            "activeTransfers" : 0, "uploadSpeed" : 0.0, "downloadSpeed" : 0.0})
    
    def connectMessenger(self, m, state):
        state.messenger.connect(m[1])
    
    def listenMessenger(self, m, state):
        state.messenger.listen(m[1])
    
    def acceptMessenger(self, m, state):
        state.messenger.accept()
    
    def disconnectMessenger(self, m, state):
        state.messenger.disconnect()
    
    def dispose(self):
        if self.pid:
            process.try_send(self.pid, "close")
            self.pid = None