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
import threading
import socket
from spark.async import Future, Delegate, asyncMethod
from spark.messaging.common import ThreadedMessenger
from spark.messaging import *

class Session(object):
    def __init__(self):
        self.__lock = threading.RLock()
        self.started = Delegate(self.__lock)
        self.ended = Delegate(self.__lock)
        self.sessionThread = None
        self.sessionSocket = None
    
    @asyncMethod
    def connect(self, address, future):
        """ Try to establish a connection with remote peer with the specified address. """
        with self.__lock:
            if self.sessionThread is None:
                self.sessionThread = threading.Thread(target=self.doConnect,
                    args=(address, future), name="Session" )
                self.sessionThread.daemon = True
                self.sessionThread.start()
    
    @asyncMethod
    def listen(self, address, future):
        """ Listen on the interface with the specified addres for a connection. """
        with self.__lock:
            if self.sessionThread is None:
                self.sessionThread = threading.Thread(target=self.doListen,
                    args=(address, future), name="Session")
                self.sessionThread.daemon = True
                self.sessionThread.start()
    
    def join(self):
        """ Wait for the session to be finished. """
        with self.__lock:
            if self.sessionThread:
                self.sessionThread.join()
    
    def doConnect(self, address, future):
        """ Thread entry point for 'connect'. """
        try:
            # establish the connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            sock.connect(address)
            with self.__lock:
                self.sessionSocket = sock
            
            # negotiate the protocol
            f = SocketFile(sock)
            negociateProtocol(f, True)
        except:
            self.threadCleanup(False)
            future.failed()
        
        messenger = ThreadedMessenger(f)
        self.sessionEstablished(messenger, future)
    
    def doListen(self, localAddress, future):
        """ Thread entry point for 'listen'. """
        try:
            # wait for an incoming connection
            listenSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            try:
                listenSock.bind(localAddress)
                listenSock.listen(1)
                sock, remoteAddress = listenSock.accept()
                with self.__lock:
                    self.sessionSocket = sock
            finally:
                listenSock.close()
            
            # negotiate the protocol
            f = SocketFile(sock)
            negociateProtocol(f, False)
        except:
            self.threadCleanup(False)
            future.failed()

        messenger = ThreadedMessenger(f)
        self.sessionEstablished(messenger, future)
    
    def sessionEstablished(self, messenger, future):
        self.started()
        future.completed()
        recvFuture = Future(self.messageReceived)
        recvFuture.messenger = messenger
        messenger.receiveMessage(recvFuture)
    
    def messageReceived(self, future):
        try:
            # handle the message that was received
            message = future.result[0]
            if message is None:
                self.threadCleanup(True)
                return
            messenger = future.messenger
            self.handleMessage(message)
            
            # start receiving the next message
            future = Future(self.messageReceived)
            future.messenger = messenger
            messenger.receiveMessage(future)
        except:
            self.threadCleanup(True)
    
    def handleMessage(self, message):
        print "Received message '%s'" % str(message)
    
    def threadCleanup(self, wasConnected):
        with self.__lock:
            self.sessionThread = None
            if self.sessionSocket:
                self.sessionSocket.shutdown(socket.SHUT_RDWR)
                self.sessionSocket.close()
                self.sessionSocket = None
        if wasConnected:
            self.ended()

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
        self.read = socket.recv
        self.write = socket.send