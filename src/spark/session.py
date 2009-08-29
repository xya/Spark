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
import sys
import traceback
import types
import threading
from Queue import Queue
import socket
from spark.async import Future, Delegate, asyncMethod
from spark.messaging.common import ThreadedMessenger
from spark.messaging import *

class Session(object):
    def __init__(self):
        self.lock = threading.RLock()
        self.conn = None
        self.thread = None
        self.queue = None
    
    @asyncMethod
    def connect(self, address, future):
        """ Try to establish a connection with remote peer with the specified address. """
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(name="Session",
                    target=self.doConnect, args=(address, future))
                self.thread.daemon = True
                self.thread.start()
            else:
                raise Exception("The current session is still active")
    
    @asyncMethod
    def listen(self, address, future):
        """ Listen on the interface with the specified addres for a connection. """
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(name="Session",
                    target=self.doListen, args=(address, future))
                self.thread.daemon = True
                self.thread.start()
            else:
                raise Exception("The current session is still active")
    
    @asyncMethod
    def disconnect(self, future):
        """ Terminate the session. """
        raise NotImplementedError()
    
    def doConnect(self, address, future):
        """ Thread entry point for 'connect'. """
        try:
            # establish the connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            sock.connect(address)
            with self.lock:
                self.conn = sock
            
            # negotiate the protocol
            f = SocketFile(sock)
            negociateProtocol(f, True)
        except:
            self.sessionCleanup()
            future.failed()
        else:
            self.sessionStarted(future, address)
    
    def doListen(self, localAddress, future):
        """ Thread entry point for 'listen'. """
        try:
            # wait for an incoming connection
            listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            try:
                listenSock.bind(localAddress)
                listenSock.listen(1)
                sock, remoteAddress = listenSock.accept()
                with self.lock:
                    self.conn = sock
            finally:
                listenSock.close()
            
            # negotiate the protocol
            f = SocketFile(sock)
            negociateProtocol(f, False)
        except:
            self.sessionCleanup()
            future.failed()
        else:
            self.sessionStarted(future, remoteAddress)
    
    def sessionCleanup(self):
        """ Close the connection and free all session-related resoources. """
        with self.lock:
            self.messenger.close()
            self.messenger = None
            self.thread = None
            self.queue = None
            if self.conn:
                self.conn.close()
                self.conn = None
    
    def sessionStarted(self, future, *args):
        """ Called when a session has been established. """
        queue = Queue(32)
        with self.lock:
            self.queue = queue
            self.messenger = ThreadedMessenger(SocketFile(self.conn))
            self.messenger.receiveMessage(Future(self.messageReceived))
            
        try:
            future.completed(*args)
            task = queue.get()
            while task is not None:
                if isinstance(task, tuple):
                    type, val, tb, fatal = task
                    print("Unhandled exception on a session thread", file=sys.stderr)
                    traceback.print_exception(type, val, tb, file=sys.stderr)
                    if fatal:
                        break
                else:
                    print("Received '%s'" % str(task))
                task = self.queue.get()
        finally:
            self.sessionCleanup()

    def messageReceived(self, future):
        try:
            message = future.result[0]
        except:
            type, val, tb = sys.exc_info()
            self.queue.put((type, val, tb, True))
            return
        # operations on queues may block, so don't use with the lock held
        with self.lock:
            queue = self.queue
        queue.put(message)
        if message is not None:
            with self.lock:
                messenger = self.messenger
            if messenger is not None:
                messenger.receiveMessage(Future(self.messageReceived))
    
    def join(self):
        """ Wait for the session to be finished. """
        with self.lock:
            thread = self.thread
        # don't call join while holding the lock, or risk deadlocking everything
        if thread:
            thread.join()

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
        self.read = socket.recv
        self.write = socket.send