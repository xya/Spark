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

import threading
from Queue import Queue
from spark import protocol
from spark.async import Future, Delegate, asyncMethod
from spark.protocol import TextMessage, Block

class Messenger(object):
    """ Base class for sending and receiving messages asynchronously. """
    
    def sendMessage(self, message, future):
        """ Send a message. """
        raise NotImplementedError()
    
    def receiveMessage(self, future):
        """ Receive a message. """
        raise NotImplementedError()

class MessageDelivery(object):
    def __init__(self, sender):
        self.sender = sender
        self.__lock = threading.Lock()
        self.requestReceived = Delegate(self.__lock)
        self.notificationReceived = Delegate(self.__lock)
        self.blockReceived = Delegate(self.__lock)
        self.nextID = 0
        self.pendingRequests = {}
    
    @asyncMethod
    def sendRequest(self, req, future):
        """ Send a request and return the response through the future. """
        if not isinstance(req, TextMessage) or (req.type != TextMessage.REQUEST):
            raise TypeError("req should be a text request.")
        with self.__lock:
            req.transID = self.nextID
            self.nextID += 1
            self.pendingRequests[req.transID] = future
        self.sender.sendMessage(req, Future())
    
    @asyncMethod
    def sendNotification(self, n, future):
        """ Send a notification. """
        if not isinstance(req, TextMessage) or (req.type != TextMessage.NOTIFICATION):
            raise TypeError("n should be a text notification.")
        with self.__lock:
            n.transID = self.nextID
            self.nextID += 1
        self.sender.sendMessage(n, future)
    
    def deliver(self, m):
        """
        Deliver a message. It could be a response to return to the request's sender.
        Or it could be a request, notification or block to publish through events.
        """
        if isinstance(m, TextMessage):
            if m.type == TextMessage.RESPONSE:
                # notifies the request's sender that the response arrived
                with self.__lock:
                    future = self.pendingRequests.pop(m.transID, None)
                if future:
                    future.completed(m)
            elif m.type == TextMessage.REQUEST:
                self.requestReceived(m)
            elif m.type == TextMessage.NOTIFICATION:
                self.notificationReceived(m)
        elif isinstance(m, Block):
            self.blockReceived(m)

class ThreadedMessenger(Messenger):
    def __init__(self, file):
        super(ThreadedMessenger, self).__init__(file)
        self.file = file
        self.sendQueue = Queue(32)
        self.receiveQueue = Queue(32)
        self.sendThread = threading.Thread(target=self.sendLoop)
        self.sendThread.daemon = True
        self.sendThread.start()
        self.receiveThread = threading.Thread(target=self.receiveLoop)
        self.receiveThread.daemon = True
        self.receiveThread.start()
    
    @asyncMethod
    def sendMessage(self, message, future):
        self.sendQueue.put((message, future))
    
    @asyncMethod
    def receiveMessage(self, future):
        self.receiveQueue.put(future)
    
    def sendLoop(self):
        writer = protocol.writer(self.file)
        while True:
            request = self.sendQueue.get()
            if request is None:
                return
            message, future = request
            try:
                writer.write(message)
                future.completed(message)
            except Exception, e:
                future.failed(e)
    
    def receiveLoop(self):
        parser = protocol.parser(self.file)
        while True:
            request = self.receiveQueue.get()
            if request is None:
                return
            future = request
            try:
                message = parser.read()
                future.completed(message)
            except Exception, e:
                future.failed(e)