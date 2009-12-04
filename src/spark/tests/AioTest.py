#!/usr/bin/env python
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

import unittest
import functools
import os
from spark.async import Future
from spark.messaging import Transport

Reactors = []

try:
    from spark.async.pollreactor import PollReactor
    Reactors.append(PollReactor)
except ImportError:
    pass
    
try:
    from spark.async.iocpreactor import CompletionPortReactor
    Reactors.append(CompletionPortReactor)
except ImportError:
    pass

TestFile = os.path.join(os.path.dirname(__file__), 'ProtocolTest.log')

def runReactors(testMethod):
    """ Run the test with all available reactors. """
    @functools.wraps(testMethod)
    def wrapper(self):
        for reactor in Reactors:
            with reactor() as rea:
                rea.launch_thread()
                testMethod(self, rea)
    return wrapper

def runReactorTypes(testMethod):
    """ Run the test with all available reactor types. """
    @functools.wraps(testMethod)
    def wrapper(self):
        for reactor in Reactors:
            testMethod(self, reactor)
    return wrapper

class PipeWrapper(object):
    """
    File-like socket encapsulating both the reading end of a pipe and
    the writing end of another pipe, much like a socket.
    """
    def __init__(self, r, w):
        self.r = r
        self.w = w
    
    def beginRead(self, size):
        return self.r.beginRead(size)
    
    def beginWrite(self, data):
        return self.r.beginWrite(data)
    
    def read(self, size):
        return self.r.read(size)
    
    def write(self, data):
        return self.r.write(data)
    
    def close(self):
        self.r.close()
        self.w.close()

class PipeTransport(Transport):
    """
    Transport which use a pipe for communications, intended for testing.
    
    This class uses an asynchronous execution model. The reactor should be used
    for all operations (I/O and non-I/O), so that the session runs on a single thread.
    """
    def __init__(self, reactor, pipe, w, name=None):
        super(PipeTransport, self).__init__()
        self.logger = logging.getLogger(name)
        self.reactor = reactor
        self.pipe = pipe
        self.remoteAddr = None
        self.connState = Transport.DISCONNECTED
    
    def connect(self, address):
        """ Try to establish a connection with a remote peer at the specified address. """
        return self.reactor.send(self._connectRequest(True))
    
    def listen(self, address):
        """ Listen on the interface with the specified addres for a connection. """
        return self.reactor.send(self._connectRequest(False))
    
    def disconnect(self):
        """ Close an established connection. """
        return self.reactor.send(self._closeConnection)
    
    @property
    def connection(self):
        """ If a connection has been established, file-like object which can be used to communicate."""
        if self.connState == Transport.CONNECTED:
            return self.pipe
        else:
            return None
    
    def _connectRequest(self, initiating):
        if (self.connState == Transport.DISCONNECTED) and pipe is not None:
            self.connState = Transport.CONNECTED
            self.reactor.post(self.onConnected, initiating)
        else:
            raise Exception("Invalid state")
    
    def _closeConnection(self):
        """ If there is an active connection, close it. """
        if self.connState == Transport.CONNECTED:
            self.logger.info("Disconnecting pipe")
            try:
                self.pipe.close()
            except Exception:
                self.logger.exception("pipe.close() failed")
            self.pipe = None
            self.connState = Transport.DISCONNECTED
            self.onDisconnected()
        else:
            wasDisconnected = False

class ReactorTest(unittest.TestCase):
    @runReactors
    def testSend(self, rea):
        """ send() should invoke the callable asynchronously and return the result """
        def bar(arg):
            return (arg, "bar")
        result = rea.send(bar, "foo").wait(1.0)
        self.assertEqual(("foo", "bar"), result)
    
    @runReactors
    def testPost(self, rea):
        """ post() should invoke the callable asynchronously """
        cont = Future()
        def complete(arg1, arg2):
            cont.completed((arg1, arg2))
        rea.post(complete, "foo", "bar")
        result = cont.wait(1.0)
        self.assertEqual(("foo", "bar"), result)

    @runReactors
    def testAsyncRead(self, rea):
        """ beginRead() should be able to read from a file. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        with rea.open(TestFile) as file:
            f = file.beginRead(19)
            f.after(read_complete)
            f.wait(1.0)
            # TODO: make it thread-safe
            self.assertEqual(1, len(results))
            self.assertEqual("0023 > list-files 0", results[0])
    
    @runReactors
    def testAsyncPipe(self, rea):
        """ beginRead() should be able to read what was written on a pipe. """
        results = []
        def read_complete(prev):
            results.append(prev.result)
        r, w = rea.pipe()
        try:
            f = r.beginRead(3)
            f.after(read_complete)
            w.write("foo")
            f.wait(1.0)
            # TODO: make it thread-safe
            self.assertEqual(1, len(results))
            self.assertEqual("foo", results[0])
        finally:
            r.close()
            w.close()

if __name__ == '__main__':
    import sys
    unittest.main(argv=sys.argv)