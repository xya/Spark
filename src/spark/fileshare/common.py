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

import types
from datetime import datetime, timedelta
from spark.async import Delegate

class FileShare(object):
    """ Base class for interacting with Spark file shares. """
    
    Requests = [
        "create-transfer", "start-transfer", "close-transfer",
        "list-files", "shutdown"
    ]
    
    Notifications = [
        "file-added", "file-removed", "transfer-state-changed", "panic"
    ]
    
    def close(self):
        """ Close the file share, terminating it and freeing resources. """
        pass
    
    def attributeName(self, tag):
        """ Return the name of the attribute used for the specified tag. """
        return toCamelCase(tag)
    
    def createRequest(self, tag, handler=None):
        """ Create a request for the specified tag. """
        name = self.attributeName(tag)
        if handler is None:
            def requestHandler(self, params):
                raise NotImplementedError("The '%s' request handler is not implemented" % tag)
            handler = types.MethodType(requestHandler, self)
        setattr(self, name, handler)
        return name
    
    def invokeRequest(self, tag, *args):
        """ Invoke the request that has the specified tag. """
        name = self.attributeName(tag)
        if hasattr(self, name):
            handler = getattr(self, name)
            if hasattr(handler, "__call__"):
                return handler(*args)
        
    def createEvent(self, tag):
        """ Create an event for the specified tag. """
        name = self.attributeName(tag)
        setattr(self, name, Delegate())
        return name
        
    def invokeEvent(self, tag, *args):
        """ Invoke the event that has the specified tag. """
        name = self.attributeName(tag)
        if hasattr(self, name):
            delegate = getattr(self, name)
            if hasattr(delegate, "__call__"):
                delegate(*args)

class TransferLocation(object):
    LOCAL = 0       # a local file is being sent
    REMOTE = 1      # a remite file is being received
    
class TransferInfo(object):
    """ Provides information about a file transfer. """
    def __init__(self, transferID, location):
        self.transferID = transferID
        self.location = location
        self.state = "created"
        self.completedSize = 0
        self.transferSpeed = 0
        self.started = None
        self.ended = None
    
    @property
    def duration(self):
        """ Return the duration of the transfer, or None if the transfer has never been started. """
        if self.started is None:
            return None
        elif self.ended is None:
            return datetime.now - self.started
        else:
            return self.ended - self.started
    
    @property
    def averageSpeed(self):
        """ Return the average transfer speed, in bytes/s. """
        duration = self.duration
        if duration is None:
            return None
        else:
            seconds = duration.seconds
            seconds += (duration.microseconds * 10e-6)
            seconds += (duration.days * 24 * 3600)
            return self.completedSize / seconds
    
    @property
    def progress(self):
        """ Return a number between 0.0 and 1.0 indicating the progress of the transfer. """
        raise NotImplementedError()
    
    @property
    def eta(self):
        """ Return an estimation of the time when the transfer will be completed. """
        raise NotImplementedError()

def toCamelCase(tag):
    """ Convert the tag to camel case (e.g. "create-transfer" becomes "createTransfer"). """
    words = tag.split("-")
    first = words.pop(0)
    words = [word.capitalize() for word in words]
    words.insert(0, first)
    return "".join(words)