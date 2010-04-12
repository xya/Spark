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
from spark.async import *
from spark.messaging import *
from spark.fileshare.service import FileShare

__all__ = ["SparkApplication"]

class SparkApplication(object):
    """ Hold the state of the whole application. """
    def __init__(self):
        self._myIPaddress = "127.0.0.1"
        self._isConnected = False
        self._activeTransfers = 0
        self._uploadSpeed = 0.0
        self._downloadSpeed = 0.0
        self._files = {}
        self.connected = Delegate()
        self.connectionError = Delegate()
        self.stateChanged = Delegate()
        self.filesUpdated = Delegate()
        self.session = FileShare()
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
        Process.send(self.runner.pid, Command("connect", address))
    
    def bind(self, address):
        Process.send(self.runner.pid, Command("bind", address))
    
    def disconnect(self):
        Process.send(self.runner.pid, Command("disconnect"))
    
    def listFiles(self, excludeRemoved=True, senderPid=None):
        """ Return a copy of the current file table, which maps file IDs to files. """
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.runner.pid, Command("list-files", excludeRemoved, senderPid))
    
    def addFile(self, path, senderPid=None):
        """ Add the local file with the given path to the list. """
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.runner.pid, Command("add-file", path, senderPid))
    
    def removeFile(self, fileID, senderPid=None):
        """ Remove the file (local or remote) with the given ID from the list. """
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.runner.pid, Command("remove-file", fileID, senderPid))
    
    def startTransfer(self, fileID, senderPid=None):
        """ Start receiving the remote file with the given ID. """
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.runner.pid, Command("start-transfer", fileID, senderPid))
    
    def stopTransfer(self, fileID, senderPid=None):
        """ Stop receiving the remote file with the given ID. """
        if not senderPid:
            senderPid = Process.current()
        Process.send(self.runner.pid, Command("stop-transfer", fileID, senderPid))
    
    @property
    def files(self):
        """ Return the current file list. """
        return self._files
    
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
    
    def installHandlers(self, matcher, pid=None):
        """ Suscribe to Spark's internal processes events so the state is kept up to date. """
        if pid == None:
            pid = Process.current()
        self.session.connected.suscribe(pid)
        self.session.connectionError.suscribe(pid)
        self.session.stateChanged.suscribe(pid)
        self.session.filesUpdated.suscribe(pid)
        matcher.addHandlers(self,
            self.session.connected.pattern,
            self.session.connectionError.pattern,
            self.session.stateChanged.pattern,
            self.session.filesUpdated.pattern,
            Event("list-files", None))
    
    def onConnected(self, m, *args):
        self.connected()
    
    def onConnectionError(self, m, error, *args):
        self.connectionError(error)
    
    def onSessionStateChanged(self, m, sessionState, *args):
        self._isConnected = sessionState["isConnected"]
        self._activeTransfers = sessionState["activeTransfers"]
        self._uploadSpeed = sessionState["uploadSpeed"]
        self._downloadSpeed = sessionState["downloadSpeed"]
        self.stateChanged()
    
    def onFilesUpdated(self, m, *args):
        self.listFiles()
    
    def onListFiles(self, m, files, *args):
        self._files = files
        self.filesUpdated()
    
    Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
    def formatSize(self, size):
        for unit, count in reversed(SparkApplication.Units):
            if size >= count:
                return "%0.2f %s" % (size / float(count), unit)
        return "%d byte" % size