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

from spark.async import Future, asyncMethod
from spark.messaging import Notification
from spark.fileshare.common import FileShare, toCamelCase

class LocalFileShare(FileShare):
    def __init__(self, delivery):
        super(RemoteFileShare, self).__init__()
        self.delivery = delivery
        self.delivery.requestReceived += self.requestReceived
    
    def requestReceived(self, req):
        """ Deliver incoming requests by invoking the relevant request handler. """
        future = Future(self.requestCompleted)
        future.request = req
        self.invokeRequest(req.tag, req.data, future)
    
    def requestCompleted(self, future):
        """ Send a response after the request is completed. """
        try:
            results = future.result
            if len(results) == 0:
                result = None
            elif len(results) == 1:
                result = results[0]
            else:
                result = results
        except Exception, e:
            result = {"error" : str(e)}
        self.delivery.sendResponse(future.request, result, Future())
    
    @asyncMethod
    def listFiles(self, params, future):
        raise NotImplementedError()
    
    @asyncMethod
    def createTransfer(self, params, future):
        raise NotImplementedError()
    
    @asyncMethod
    def startTransfer(self, params, future):
        raise NotImplementedError()
    
    @asyncMethod
    def closeTransfer(self, params, future):
        raise NotImplementedError()
    
    @asyncMethod
    def shutdown(self, params, future):
        raise NotImplementedError()
    
    @asyncMethod
    def notifyEvent(self, tag, params, future):
        """ Notify the remote peer and local observers of an event. """
        self.invokeEvent(tag, params)
        self.delivery.sendNotification(Notification(tag, params), future)
    
    def addLocalFile(self, path):
        raise NotImplementedError()
    
    def removeLocalFile(self, fileID):
        raise NotImplementedError()