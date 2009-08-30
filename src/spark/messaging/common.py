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
        
    def sendMessage(self, message, future):
        """ Send a message. """
        raise NotImplementedError()
    
    def receiveMessage(self, future):
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
        self.resetDelivery()
    
    @asyncMethod
    def sendRequest(self, req, future):
        """ Send a request and return the response through the future. """
        if not hasattr(req, "type") or (req.type != TextMessage.REQUEST):
            raise TypeError("req should be a text request.")
        with self.__lock:
            req.transID = self.nextID
            self.nextID += 1
            self.pendingRequests[req.transID] = future
        self.sendMessage(req, Future())
    
    @asyncMethod
    def sendResponse(self, req, params, future):
        """ Respond to a request. """
        if not hasattr(req, "type") or (req.type != TextMessage.REQUEST):
            raise TypeError("req should be a text request.")
        response = Response(req.tag, params, req.transID)
        self.sendMessage(response, future)
    
    @asyncMethod
    def sendNotification(self, n, future):
        """ Send a notification. """
        if not hasattr(n, "type") or (n.type != TextMessage.NOTIFICATION):
            raise TypeError("n should be a text notification.")
        with self.__lock:
            n.transID = self.nextID
            self.nextID += 1
        self.sendMessage(n, future)
    
    def resetDelivery(self):
        """ Reset the state of message delivery."""
        with self.__lock:
            self.requestReceived = Delegate(self.__lock)
            self.notificationReceived = Delegate(self.__lock)
            self.blockReceived = Delegate(self.__lock)
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
                    future = self.pendingRequests.pop(m.transID, None)
                if future:
                    future.completed(m)
            elif m.type == TextMessage.REQUEST:
                self.requestReceived(m)
            elif m.type == TextMessage.NOTIFICATION:
                self.notificationReceived(m)
        elif hasattr(m, "blockID"):
            self.blockReceived(m)

class ThreadedMessenger(Messenger):
    def __init__(self, file):
        super(ThreadedMessenger, self).__init__()
        self.file = file
        self.sendQueue = BlockingQueue(32)
        self.receiveQueue = BlockingQueue(32)
        self.sendThread = threading.Thread(target=self.sendLoop, name="MessageSender")
        self.sendThread.daemon = True
        self.sendThread.start()
        self.receiveThread = threading.Thread(target=self.receiveLoop, name="MessageReceiver")
        self.receiveThread.daemon = True
        self.receiveThread.start()
    
    def close(self):
        self.sendQueue.close()
        self.receiveQueue.close()
        self.sendThread.join()
        self.receiveThread.join()
    
    @asyncMethod
    def sendMessage(self, message, future):
        self.sendQueue.put((message, future))
    
    @asyncMethod
    def receiveMessage(self, future):
        self.receiveQueue.put(future)
    
    def sendLoop(self):
        writer = messageWriter(self.file)
        try:
            while True:
                message, future = self.sendQueue.get()
                try:
                    future.run(writer.write, message)
                except:
                    print("A future's callback raised an exception", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
        except QueueClosedError:
            pass
    
    def receiveLoop(self):
        parser = messageReader(self.file)
        try:
            while True:
                future = self.receiveQueue.get()
                try:
                    future.run(parser.read)
                except:
                    print("A future's callback raised an exception", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
        except QueueClosedError:
            pass

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
    
    @threadedMethod
    def sendMessage(self, message):
        with self.writeLock:
            self.writer.write(message)
    
    @threadedMethod
    def receiveMessage(self):
        with self.readLock:
            return self.reader.read()