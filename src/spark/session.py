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
import socket
from spark.async import Future, Delegate, BlockingQueue, QueueClosedError, asyncMethod
from spark.messaging.common import ThreadedMessenger, AsyncMessenger
from spark.messaging import *

class Session(object):
    def __init__(self):
        super(Session, self).__init__()
        # all attributes except queue are protected by the lock
        # invariants:
        # (1)   'thread != None' means the session has started
        # (2)   'joinList != None' and 'messenger != None' means the session is active
        # (3)   'joinList != None' and 'messenger == None' means the session is closing
        self.lock = threading.RLock()
        self.conn = None
        self.thread = None
        self.joinList = None
        # Using the queue is only allowed if (2) is true
        self.queue = BlockingQueue(32, False, self.lock)
    
    @asyncMethod
    def connect(self, address, future):
        """ Try to establish a connection with a remote peer with the specified address. """
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
        """ Terminate the session if it is active. """
        with self.lock:
            if self.thread is not None:
                if self.joinList is None:
                    starting = True
                else:
                    starting = False
                    self.joinList.append(future)
                    if self.messenger is not None:
                        self.queue.close()
        if starting:
            raise NotImplementedError("Can't close a session which is still starting")
    
    @asyncMethod
    def join(self, future):
        """ Wait for the session to be finished if it is active. """
        inactive = True
        with self.lock:
            if self.joinList is not None:
                self.joinList.append(future)
                inactive = False
        if inactive:
            future.completed(False)
    
    def doConnect(self, address, future):
        """ Thread entry point for 'connect'. """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            sock.connect(address)
            negociateProtocol(SocketFile(sock), True)
        except:
            future.failed()
        else:
            self.messageLoop(sock, future, address)
    
    def doListen(self, localAddress, future):
        """ Thread entry point for 'listen'. """
        try:
            listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            try:
                listenSock.bind(localAddress)
                listenSock.listen(1)
                conn, remoteAddress = listenSock.accept()
            finally:
                listenSock.close()
            negociateProtocol(SocketFile(conn), False)
        except:
            future.failed()
        else:
            self.messageLoop(conn, future, remoteAddress)
    
    def messageLoop(self, conn, future, *args):
        with self.lock:
            self.conn = conn
            self.joinList = []
            self.queue.open()
            self.messenger = AsyncMessenger(SocketFile(self.conn))
            self.messenger.receiveMessage(Future(self.messageReceived))
        
        try:
            future.completed(*args)
            self.sessionStarted()
            task = self.queue.get()
            while True:
                self.handleMessage(task)
                task = self.queue.get()
        except QueueClosedError:
            pass
        except:
            print("Unhandled exception in the message loop", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        finally:
            self.sessionCleanup()
    
    def sessionStarted(self):
        """ Called when a session has started, that is messages can be sent and received. """
        pass
    
    @asyncMethod
    def sendMessage(self, m, future):
        """ Send a message to the remote peer. """
        with self.lock:
            if self.messenger is None:
                future.failed(Exception("The current session is not active, can't send messages"))
            else:
                self.messenger.sendMessage(m, future)
    
    def handleMessage(message):
        """ Do something with a message that was received. """
        pass

    def messageReceived(self, future):
        try:
            message = future.result[0]
        except:
            message = None
            traceback.print_exc(file=sys.stderr)
        with self.lock:
            if self.messenger is not None:
                if message is None:
                    self.queue.close(True)
                else:
                    self.queue.put(message)
                    self.messenger.receiveMessage(Future(self.messageReceived))

    def sessionCleanup(self):
        """ Close the connection and free all session-related resources. """
        # close the connection and messenger
        with self.lock:
            conn, self.conn = self.conn, None
            messenger, self.messenger = self.messenger, None
            self.queue.close()
        if conn:
            conn.close()
        if messenger and hasattr(messenger, "close"):
            messenger.close()
        
        # stop the session and call futures queued by join and disconnect
        with self.lock:
            self.thread = None
            joinList, self.joinList = self.joinList[:], None
        if joinList is not None:
            for future in joinList:
                future.completed()

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
    
    def read(self, size):
        try:
            return self.socket.recv(size)
        except socket.error as e:
            if e.errno == 104:      # connection reset by peer
                return ""
            else:
                raise
    
    def write(self, data):
        return self.socket.send(data)