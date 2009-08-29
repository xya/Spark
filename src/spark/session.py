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
        self.joinList = []
        self.sessionSocket = None
        self.messenger = None
    
    @asyncMethod
    def connect(self, address, future):
        """ Try to establish a connection with remote peer with the specified address. """
        with self.__lock:
            if self.sessionSocket is None:
                sessionThread = threading.Thread(name="Session",
                    target=self.doConnect, args=(address, future))
                sessionThread.daemon = True
                sessionThread.start()
            else:
                raise Exception("The current session is still active")
    
    @asyncMethod
    def listen(self, address, future):
        """ Listen on the interface with the specified addres for a connection. """
        with self.__lock:
            if self.sessionSocket is None:
                sessionThread = threading.Thread(name="Session",
                    target=self.doListen, args=(address, future))
                sessionThread.daemon = True
                sessionThread.start()
            else:
                raise Exception("The current session is still active")
    
    @asyncMethod
    def join(self, future):
        """ Wait for the session to be finished. """
        with self.__lock:
            if self.sessionSocket:
                self.joinList.append(future)
            else:
                future.completed()
    
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
            self.sessionCleanup(True)
            future.failed()
            
        future.completed()
        with self.__lock:
            self.messenger = ThreadedMessenger(f)
            self.messenger.receiveMessage(Future(self.messageReceived))
    
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
            self.sessionCleanup(True)
            future.failed()
            
        future.completed(remoteAddress)
        with self.__lock:
            self.messenger = ThreadedMessenger(f)
            self.messenger.receiveMessage(Future(self.messageReceived))
    
    def messageReceived(self, future):
        try:
            message = future.result[0]
        except:
            self.sessionCleanup(True)
        if message is None:
            self.sessionCleanup(False)
        else:
            self.handleMessage(message)
            with self.__lock:
                self.messenger.receiveMessage(Future(self.messageReceived))
    
    def handleMessage(self, message):
        print "Received message '%s'" % str(message)
    
    def sessionCleanup(self, fail):
        futures = []
        with self.__lock:
            if self.sessionSocket:
                self.sessionSocket.shutdown(socket.SHUT_RDWR)
                self.sessionSocket.close()
                self.sessionSocket = None
                futures.extend(self.joinList)
                
        for future in futures:
            if fail:
                future.failed()
            else:
                future.completed()

class SparkSession(Session):
    def __init__(self):
        super(SparkSession, self).__init__()

class SocketFile(object):
    def __init__(self, socket):
        self.socket = socket
        self.read = socket.recv
        self.write = socket.send