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
import os
import traceback
import types
import threading
import socket
from spark.async import Future, Delegate, BlockingQueue, QueueClosedError
from spark.messaging.common import ThreadedMessenger, AsyncMessenger
from spark.messaging import *

__all__ = ["Session", "SessionTask"]

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
        self.messenger = None
        self.joinList = None
        # Using the queue is only allowed if (2) is true
        self.queue = BlockingQueue(32, False, self.lock)
    
    def connect(self, address):
        """ Try to establish a connection with a remote peer with the specified address. """
        with self.lock:
            if self.thread is None:
                cont = Future()
                self.thread = threading.Thread(name="Session",
                    target=self.threadEntry, args=(address, True, cont))
                self.thread.daemon = True
                self.thread.start()
                return cont
            else:
                raise Exception("The current session is still active")
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        with self.lock:
            if self.thread is None:
                cont = Future()
                self.thread = threading.Thread(name="Session",
                    target=self.threadEntry, args=(address, False, cont))
                self.thread.daemon = True
                self.thread.start()
                return cont
            else:
                raise Exception("The current session is still active")
    
    def disconnect(self):
        """ Terminate the session if it is active. """
        with self.lock:
            if self.thread is not None:
                if self.joinList is None:
                    raise NotImplementedError("Can't close a session which is still starting")
                else:
                    cont = Future()
                    self.joinList.append(cont)
                    if self.messenger is not None:
                        self.queue.close()
                    return cont
            else:
                return Future.done()
    
    def join(self):
        """ Wait for the session to be finished if it is active. """
        with self.lock:
            if self.joinList is not None:
                cont = Future()
                self.joinList.append(cont)
                return cont
            else:
                return Future.done(False)
    
    def threadEntry(self, address, initiating, cont):
        """ Thread entry point for 'connect'. """
        started = False
        try:
            # establish a connection and a protocol
            conn, remoteAddress = self.establishConnection(address, initiating)
            negociateProtocol(SocketFile(conn), initiating)
            
            # initialize the session, including derived classes' sessionStarted()
            with self.lock:
                self.conn = conn
                self.joinList = []
                self.queue.open()
                self.messenger = ThreadedMessenger(SocketFile(conn))
                recvCont = self.messenger.receiveMessage()
            self.sessionStarted()
            started = True
            cont.completed(remoteAddress)
            
            # enter the main loop
            recvCont.after(self.messageReceived)
            for task in self.queue:
                self.handleTask(task)
        except:
            if started:
                traceback.print_exc()
            else:
                cont.failed()
        finally:
            self.sessionCleanup()
    
    def establishConnection(self, address, initiating):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        if initiating:
            sock.connect(address)
            return sock, address
        else:
            try:
                sock.bind(address)
                sock.listen(1)
                return sock.accept()
            finally:
                sock.close()
    
    def sessionStarted(self):
        """ Called when a session has started, that is messages can be sent and received. """
        pass
    
    def sendMessage(self, m):
        """ Send a message to the remote peer. """
        with self.lock:
            if self.messenger is None:
                return Future.error(Exception(
                    "The current session is not active, can't send messages"))
            else:
                return self.messenger.sendMessage(m)
    
    def handleTask(task):
        """ Do something with a task that was submitted. """
        pass

    def messageReceived(self, prev):
        try:
            message = prev.result
        except:
            message = None
            traceback.print_exc()
        with self.lock:
            if self.messenger is not None:
                if message is None:
                    self.queue.close(True)
                else:
                    self.queue.put(HandleMessageTask(message))
                    self.messenger.receiveMessage().after(self.messageReceived)

    def submitTask(self, task):
        """ Submit a task for execution during an active session. """
        with self.lock:
            if self.messenger is None:
                raise Exception("The current session is not active")
            else:
                self.queue.put(task)

    def sessionCleanup(self):
        """ Close the connection and free all session-related resources. """
        # close the connection and messenger
        with self.lock:
            conn, self.conn = self.conn, None
            messenger, self.messenger = self.messenger, None
            self.queue.close()
        if conn:
            # force threads blocked on recv (and send?) to return
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except:
                pass
            conn.close()
        if messenger and hasattr(messenger, "close"):
            messenger.close()
        
        # stop the session and call futures queued by join and disconnect
        with self.lock:
            self.thread = None
            joinList, self.joinList = self.joinList, None
        if joinList is not None:
            for future in joinList:
                future.completed()

class HandleMessageTask(object):
    """ Task of handling a message that was received. """
    def __init__(self, message):
        self.message = message

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
    
    def read(self, size):
        try:
            return self.socket.recv(size)
        except socket.error as e:
            if e.errno == os.errno.ECONNRESET:
                return ""
            else:
                raise
    
    def write(self, data):
        return self.socket.send(data)