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
from spark.future import Future

class Messenger(object):
    """ Base class for sending and receiving messages (synchronously or not). """
    
    def __init__(self, file):
        """ Create a new messenger wrapping the file-like object. """
        self.file = file
        
    def sendMessage(self, message, future=None):
        """
        Send a message.
        Blocks until the message is sent, unless future is not None.
        """
        raise NotImplementedError()
    
    def receiveMessage(self, future=None):
        """
        Receive a message.
        Blocks until a message is received, unless future is not None.
        """
        raise NotImplementedError()

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
    
    def sendMessage(self, message, future=None):
        if future is None:
            future = Future()
            self.sendMessage(message, future)
            return future.result
        elif not future.pending:
            raise ValueError("The future object has been used already")
        self.sendQueue.put((message, future))
    
    def receiveMessage(self, future=None):
        if future is None:
            future = Future()
            self.receiveMessage(future)
            return future.result
        elif not future.pending:
            raise ValueError("The future object has been used already")
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