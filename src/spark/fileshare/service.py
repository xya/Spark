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

from types import MethodType
import threading
from spark.async import Future, Delegate
from spark.messaging import MessengerService, MessageDelivery, Request, Notification

__all__ = ["FileShare"]

def toCamelCase(tag):
    """ Convert the tag to camel case (e.g. "create-transfer" becomes "createTransfer"). """
    words = tag.split("-")
    first = words.pop(0)
    words = [word.capitalize() for word in words]
    words.insert(0, first)
    return "".join(words)

def toPascalCase(tag):
    """ Convert the tag to Pascal case (e.g. "create-transfer" becomes "CreateTransfer"). """
    return "".join([word.capitalize() for word in tag.split("-")])

REQ_LIST_FILES = "list-files"
NOT_FILE_ADDED = "file-added"
NOT_FILE_REMOVED = "file-removed"

class FileShare(MessengerService, MessageDelivery):
    """ Service that shares files over a network. """
    def __init__(self):
        super(FileShare, self).__init__()
        self.messageReceived = self.deliverMessage
        self.fileAdded = Delegate()
        self.fileRemoved = Delegate()
        self.remoteNotifications = False
    
    def files(self):
        """ Return the current file table, which maps file IDs to files. """
        raise NotImplementedError()
    
    def addFile(self, path):
        """ Add the local file with the given path to the list. """
        raise NotImplementedError()
        self.fileAdded()
        if self.remoteNotifications and self.isSessionActive:
            self.sendNotification(Notification(NOT_FILE_ADDED))
    
    def removeFile(self, fileID):
        """ Remove the file (local or remote) with the given ID from the list. """
        raise NotImplementedError()
        self.fileRemoved()
        if self.remoteNotifications and self.isSessionActive:
            self.sendNotification(Notification(NOT_FILE_REMOVED))
    
    def sessionStarted(self):
        req = Request(REQ_LIST_FILES, {'register': True})
        self.sendRequest(req).after(self._listFilesResponse)
    
    def sessionEnded(self):
        try:
            self.resetDelivery()
        finally:
            super(FileShare, self).sessionEnded()
    
    def _listFilesResponse(self, prev):
        files = prev.result
        # TODO: do something with the file table
    
    def requestReceived(self, req):
        methodName = "_request" + toPascalCase(req.tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
        else:
            def method(req):
                raise NotImplementedError()
        try:
            method(req)
        except Exception as e:
            self.sendResponse(req, {"error":
                {"type": e.__class__.__name__, "message": str(e)}
            })
    
    def notificationReceived(self, n):
        methodName = "_notification" + toPascalCase(n.tag)
        if hasattr(self, methodName):
            method = getattr(self, methodName)
            method(n)
    
    def blockReceived(self, m):
        pass
    
    def _requestListFiles(self, req):
        if (isinstance(req.params, dict)
            and req.params.has_key("register") and req.params["register"] is True):
            self.remoteNotifications = True
        self.sendResponse(req, self.files())
    
    def _notificationFileAdded(self, n):
        self.fileAdded()
    
    def _notificationFileRemoved(self, n):
        self.fileRemoved()