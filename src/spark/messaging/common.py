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

from __future__ import print_function
import traceback
import sys
import threading
from spark.async import *
from spark.messaging.protocol import messageReader, messageWriter
from spark.messaging.messages import *

__all__ = ["Messenger", "MessageDelivery"]

class Messenger(object):
    """ Base class for sending and receiving messages asynchronously. """
    def __init__(self):
        super(Messenger, self).__init__()
        
    def sendMessage(self, message):
        """ Send a message. """
        raise NotImplementedError()
    
    def receiveMessage(self):
        """ Receive a message. """
        raise NotImplementedError()

class MessageDelivery(object):
    """
    Higher-level mixin for Messenger, which can be used for handling specialized messages
    like requests, responses and notifications.
    
    Received message should be passed to deliverMessage().
    """
    def __init__(self):
        super(MessageDelivery, self).__init__()
        self.__lock = threading.Lock()
        self.requestReceived = Delegate(self.__lock)
        self.notificationReceived = Delegate(self.__lock)
        self.blockReceived = Delegate(self.__lock)
        self.nextID = 0
        self.pendingRequests = {}
    
    def sendRequest(self, req):
        """ Send a request and return the response through the continuation (Future). """
        if not hasattr(req, "type") or (req.type != TextMessage.REQUEST):
            raise TypeError("req should be a text request.")
        cont = Future()
        with self.__lock:
            req.transID = self.nextID
            self.nextID += 1
            self.pendingRequests[req.transID] = cont
        self.sendMessage(req)
        return cont
    
    def sendResponse(self, req, params):
        """ Respond to a request. """
        if not hasattr(req, "type") or (req.type != TextMessage.REQUEST):
            raise TypeError("req should be a text request.")
        response = Response(req.tag, params, req.transID)
        return self.sendMessage(response)
    
    def sendNotification(self, n):
        """ Send a notification. """
        if not hasattr(n, "type") or (n.type != TextMessage.NOTIFICATION):
            raise TypeError("n should be a text notification.")
        with self.__lock:
            n.transID = self.nextID
            self.nextID += 1
        return self.sendMessage(n)
    
    def resetDelivery(self):
        """ Reset the state of message delivery."""
        with self.__lock:
            for transID, future in self.pendingRequests.iteritems():
                try:
                    future.cancel()
                except:
                    traceback.print_exc()
            self.nextID = 0
            self.pendingRequests = {}
    
    def deliverMessage(self, m):
        """
        Deliver a message. It could be a response to return to the request's sender.
        Or it could be a request, notification or block to publish through events.
        """
        if hasattr(m, "type"):
            if m.type == TextMessage.RESPONSE:
                # notifies the request's sender that the response arrived
                with self.__lock:
                    cont = self.pendingRequests.pop(m.transID, None)
                if cont:
                    cont.completed(m)
            elif m.type == TextMessage.REQUEST:
                self.requestReceived(m)
            elif m.type == TextMessage.NOTIFICATION:
                self.notificationReceived(m)
        elif hasattr(m, "blockID"):
            self.blockReceived(m)

class AsyncMessenger(Messenger):
    def __init__(self, file):
        super(AsyncMessenger, self).__init__()
        self.file = file
        self.reader = messageReader(file)
        self.readLock = threading.Lock()
        self.writer = messageWriter(file)
        self.writeLock = threading.Lock()
    
    def close(self):
        pass
    
    def sendMessage(self, message):
        with self.writeLock:
            return self.writer.write(message)
    
    def receiveMessage(self):
        with self.readLock:
            return self.reader.read()