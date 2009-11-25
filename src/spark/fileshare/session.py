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
from spark.async import Future
from spark.messaging import SparkService
from spark.messaging import MessageDelivery
from spark.fileshare.common import FileShare
from spark.fileshare.local import LocalFileShare
from spark.fileshare.remote import RemoteFileShare

__all__ = ["FileShareSession"]

class FileShareSession(SparkService, MessageDelivery):
    def __init__(self):
        super(FileShareSession, self).__init__()
        self.__shareLock = threading.RLock()
        self.__localShare = None
        self.__remoteShare = None
        self.__localProxy = None
    
    @property
    def localShare(self):
        with self.__shareLock:
            return self.__localProxy
    
    @property
    def remoteShare(self):
        with self.__shareLock:
            return self.__remoteShare
    
    def handleTask(self, task):
        if hasattr(task, "message"):
            #print("Received '%s'" % str(task.message))
            self.deliverMessage(task.message)
        elif hasattr(task, "invoke"):
            task.invoke()
    
    def sessionStarted(self):
        with self.__shareLock:
            self.__localShare = LocalFileShare(self)
            self.__remoteShare = RemoteFileShare(self)
            self.__localProxy = FileShareProxy(self.__localShare, self)
    
    def sessionCleanup(self):
        try:
            with self.__shareLock:
                self.__localProxy = None
                if self.__remoteShare:
                    self.__remoteShare.close()
                if self.__localShare:
                    self.__localShare.close()
            self.resetDelivery()
        finally:
            super(FileShareSession, self).sessionCleanup()

class InvokeRequestTask(object):
    """ Task of invoking a request on a file share's thread. """
    def __init__(self, share, tag, params, cont):
        self.share = share
        self.tag = tag
        self.params = params
        self.cont = cont
    
    def invoke(self):
        self.share.invokeRequest(self.tag, self.params).after(self.cont)

class FileShareProxy(FileShare):
    """ Proxy which submits requests to the session's queue, so they are executed on the session's thread. """
    def __init__(self, share, session):
        super(FileShareProxy, self).__init__()
        self.share = share
        self.session = session
        for tag in FileShare.Notifications:
            name = self.attributeName(tag)
            setattr(self, name, getattr(share, name))
        for tag in FileShare.Requests:
            self.createRequest(tag, self.requestHandler(tag))
    
    def requestHandler(self, tag):
        """ Create a function to handle sending requests with the given tag """
        def handler(self, params):
            cont = Future()
            self.session.submitTask(InvokeRequestTask(self.share, tag, params, cont))
            return cont
        return MethodType(handler, self)