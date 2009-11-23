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

from spark.async import Future
from spark.messaging import Notification
from spark.fileshare.common import FileShare, toCamelCase

class LocalFileShare(FileShare):
    def __init__(self, delivery):
        super(LocalFileShare, self).__init__()
        self.publicRequests = FileShare.Requests
        self.delivery = delivery
        self.delivery.requestReceived += self.requestReceived
        for tag in FileShare.Notifications:
            self.createEvent(tag)
    
    def requestReceived(self, req):
        """ Deliver incoming requests by invoking the relevant request handler. """
        # only allow public requests to be executed remotely
        if req.tag in self.publicRequests:
            self.invokeRequest(req.tag, req.params).after(self.requestCompleted, req)
        else:
            self.requestCompleted(Future.done({"error" : "not-authorized"}), req)
    
    def requestCompleted(self, prev, request):
        """ Send a response after the request is completed. """
        try:
            results = prev.results
            if len(results) == 0:
                result = None
            elif len(results) == 1:
                result = results[0]
            else:
                result = results
        except Exception as e:
            result = {"error" : str(e)}
        self.delivery.sendResponse(request, result)
    
    def listFiles(self, params):
        files = {"123abc" : {"id": "123abc", "name": "Report.pdf", "size": 3145728, "last-modified": "20090619T173529.000Z"}}
        return Future.done(files)
    
    def createTransfer(self, params):
        raise NotImplementedError()
    
    def startTransfer(self, params):
        raise NotImplementedError()
    
    def closeTransfer(self, params):
        raise NotImplementedError()
    
    def shutdown(self, params):
        raise NotImplementedError()
    
    def notifyEvent(self, tag, params):
        """ Notify the remote peer and local observers of an event. """
        self.invokeEvent(tag, params)
        return self.delivery.sendNotification(Notification(tag, params))
    
    def addLocalFile(self, params):
        raise NotImplementedError()
    
    def removeLocalFile(self, params):
        raise NotImplementedError()