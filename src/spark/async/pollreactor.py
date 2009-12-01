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

import sys
import os
import fcntl
import select
import threading
import socket
import logging
from spark.async import Future, BlockingQueue, QueueClosedError, Delegate
from spark.async.aio import Reactor

__all__ = ["blocking_mode", "PollReactor"]

LOG_VERBOSE = 5

def blocking_mode(fd, blocking=None):
    flag = os.O_NONBLOCK
    old_mode = fcntl.fcntl(fd, fcntl.F_GETFL, flag)
    if blocking is not None:
        if blocking:
            new_mode = (old_mode & ~flag)
        else:
            new_mode = (old_mode | flag)
        fcntl.fcntl(fd, fcntl.F_SETFL, new_mode)
    return (old_mode & flag) == 0

class PollReactor(Reactor):
    def __init__(self, name=None, lock=None):
        self.logger = logging.getLogger(name)
        if lock:
            self.lock = lock
        else:
            self.lock = threading.RLock()
        self.queue = BlockingQueue(64, lock=self.lock)
        self.pending = {}
        self.onClosed = Delegate(self.lock)
        self.active = False
        self.thread = None
        self.req_r, self.req_w = os.pipe()
        blocking_mode(self.req_r, False)
        blocking_mode(self.req_w, False)
    
    def socket(self, family, type, proto):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        return NonBlockingSocket.socket(self, family, type, proto)
    
    def open(self, file, mode=None):
        """ Open a file that uses the reactor to do asynchronous I/O. """
        return NonBlockingFile.open(self, file, mode)
    
    def pipe(self):
        """ Create a pipe that uses the reactor to do asynchronous I/O. """
        r, w = os.pipe()
        blocking_mode(r, False)
        blocking_mode(w, False)
        return NonBlockingFile(self, r), NonBlockingFile(self, w)
    
    def send(self, fun, *args, **kwargs):
        """ Invoke a callable on the reactor's thread and return its result through a future. """
        if fun is None:
            raise TypeError("The callable must not be None")
        cont = Future()
        with self.lock:
            invokeDirectly = (self.thread == threading.currentThread())
        if invokeDirectly:
            cont.run(fun, *args, **kwargs)
        else:
            self.submit(InvokeOperation(self, cont, fun, args, kwargs))
        return cont
    
    def post(self, fun, *args, **kwargs):
        """ Submit a callable to be invoked on the reactor's thread later. """
        if fun is None:
            raise TypeError("The callable must not be None")
        self.submit(InvokeOperation(self, None, fun, args, kwargs), True)
    
    def launch_thread(self):
        """ Start a background I/O thread to run the reactor. """
        with self.lock:
            if self.active is False:
                self.active = True
                self.thread = threading.Thread(target=self.eventLoop, name="I/O thread")
                self.thread.daemon = True
                self.thread.start()
                return True
            else:
                return False
    
    def run(self):
        """ Run the reactor on the current thread. """
        with self.lock:
            if self.active is False:
                self.active = True
                self.thread = threading.currentThread()
            else:
                return
        self.eventLoop()
    
    def submit(self, op, forceAsync=False):
        """
        Submit an I/O request to be performed asynchronously. If submit() is
        called on the reactor's thread the operation will be started immediatly;
        otherwise it will be started when it gets dequeued by the reactor's thread.
        """
        with self.lock:
            executeDirectly = (self.thread == threading.currentThread())
        if not forceAsync and executeDirectly:
            self.logger.log(LOG_VERBOSE, "Executing operation %s" % str(op))
            self.execute(op, False)
        else:
            self.logger.log(LOG_VERBOSE, "Submitting operation %s" % str(op))
            self.queue.put(op)
            os.write(self.req_w, '\0')
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        with self.lock:
            if self.req_w is not None:
                os.close(self.req_w)
                self.req_w = None
        self.queue.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()
    
    def cleanup(self):
        self.logger.debug("Reactor shutting down")
        with self.lock:
            os.close(self.req_r)
            self.req_r = None
            if self.req_w:
                os.close(self.req_w)
                self.req_w = None
        self.queue.close()
        for fd, op_queue in self.pending.iteritems():
            for op in op_queue:
                op.canceled()
        self.pending = {}
        with self.lock:
            self.active = False
            self.thread = None
        try:
            self.onClosed()
        except Exception:
            self.logger.exception("onClosed() failed")
    
    def eventLoop(self):
        try:
            self.poll = select.poll()
            self.queue.put(PipeReadOperation(self, self.req_r))
            self.empty_queue()
            while True:
                self.logger.log(LOG_VERBOSE, "Waiting for poll()")
                events = self.poll.poll()
                self.logger.log(LOG_VERBOSE, "Woke up from poll() with %s" % repr(events))
                for fd, event in events:
                     self.perform_io(fd, event)
        except QueueClosedError:
            pass
        finally:
            self.cleanup()
    
    def empty_queue(self):
        for op in self.queue.iter_nowait():
            self.execute(op, False)
    
    def execute(self, op, scheduled):
        try:
            finished = op.complete()
        except Exception:
            op.failed()
        else:
            if finished:
                if scheduled:
                    self.remove_op(op)
                op.completed()
            elif not scheduled:
                self.schedule(op)
    
    def schedule(self, op):
        events = op.event
        if not self.pending.has_key(op.fd):
            self.pending[op.fd] = [op]
        else:
            op_queue = self.pending[op.fd]
            for op in op_queue:
                events = events | op.event
            op_queue.append(op)
        self.poll.register(op.fd, events)

    def perform_io(self, fd, event):
        hangup = (event & select.POLLHUP) != 0
        error = (event & select.POLLERR) != 0
        invalid = (event & select.POLLNVAL) != 0
        if hangup or error or invalid:
            for op in self.pending[fd]:
                op.canceled(event)
            self.poll.unregister(fd)
            del self.pending[fd]
            if fd == self.req_r:
                raise QueueClosedError()
        else:
            found = None
            for op in self.pending[fd]:
                if (op.event & event) != 0:
                    found = op
                    break
            if found is not None:
                self.execute(found, True)
    
    def remove_op(self, op):
        op_queue = self.pending[op.fd]
        op_queue.remove(op)
        if len(op_queue) == 0:
            self.poll.unregister(op.fd)
            del self.pending[op.fd]

def _beginRead(reactor, fd, size):
    cont = Future()
    op = ReadOperation(reactor, fd, size, cont)
    reactor.submit(op)
    return cont

def _beginWrite(reactor, fd, data):
    cont = Future()
    op = WriteOperation(reactor, fd, data, cont)
    reactor.submit(op)
    return cont

class IOOperation(object):
    def __init__(self, reactor):
        self.reactor = reactor
        
    def complete(self):
        raise NotImplementedError()
    
    def init_file(self, file):
        """ Init the fd attribute. 'file' can either be a file or a file descriptor. """
        if hasattr(file, "fileno"):
            self.fd = file.fileno()
        else:
            self.fd = file
    
    def canceled(self, event=None):
        self.raise_canceled()
    
    def failed(self):
        self.raise_failed()
    
    def completed(self):
        self.raise_completed()
    
    def raise_completed(self, result=None):
        self.reactor.logger.log(LOG_VERBOSE, "Completed operation %s" % str(self))
        try:
            self.cont.completed(result)
        except Exception:
            self.reactor.logger.exception("Error in I/O completed() callback")
    
    def raise_failed(self):
        self.reactor.logger.debug("Failed operation of %s" % str(self))
        try:
            self.cont.failed()
        except Exception:
            self.reactor.logger.exception("Error in I/O failed() callback")
    
    def raise_canceled(self):
        self.reactor.logger.debug("Canceled operation of %s" % str(self))
        try:
            self.cont.cancel()
        except Exception:
            self.reactor.logger.exception("Error in I/O canceled() callback")
    
    def nonblock(self, func, args=(), errno=os.errno.EAGAIN):
        try:
            result = func(*args)
            return (True, result)
        except:
            e = sys.exc_info()[1]
            if hasattr(e, "errno") and (e.errno == errno):
                return (False, None)
            else:
                raise

class InvokeOperation(IOOperation):
    def __init__(self, reactor, cont, fun, args, kwargs):
        super(InvokeOperation, self).__init__(reactor)
        self.cont = cont
        self.fun = fun
        self.args = args
        self.kwargs = kwargs
    
    def __str__(self):
        args = [repr(arg) for arg in self.args]
        for key, val in self.kwargs:
            args.append("%s=%s" % (key, repr(val)))
        return "InvokeOperation(%s)" % ", ".join(args)
    
    def complete(self):
        return True
    
    def completed(self):
        self.reactor.logger.log(LOG_VERBOSE, "Completed operation %s" % str(self))
        if self.cont is None:
            try:
                self.fun(*self.args, **self.kwargs)
            except Exception:
                self.reactor.logger.exception("Error in non-I/O callback")
        else:
            self.cont.run(self.fun, *self.args, **self.kwargs)

class PipeReadOperation(IOOperation):
    def __init__(self, reactor, fd):
        super(PipeReadOperation, self).__init__(reactor)
        self.fd = fd
        self.event = select.POLLIN
    
    def complete(self):
        while True:
            success, data = self.nonblock(os.read, (self.fd, 64))
            if not success or (len(data) < 64):
                break
        self.reactor.empty_queue()
        return False
    
    def canceled(self, event=None):
        pass
    
    def failed(self):
        pass
        
    def completed(self):
        pass

class ReadOperation(IOOperation):
    def __init__(self, reactor, file, size, cont):
        super(ReadOperation, self).__init__(reactor)
        self.event = select.POLLIN
        self.init_file(file)
        self.data = []
        self.left = size
        self.cont = cont
    
    def complete(self):
        success, data = self.nonblock(os.read, (self.fd, self.left, ))
        if success:
            if len(data) > 0:
                self.data.append(data)
                self.left -= len(data)
                return self.left == 0
            else:
                # end of file or we got disconnected
                self.left = 0
                return True
        else:
            return False
    
    def canceled(self, event=None):
        self.left = 0
        self.raise_completed("")
    
    def completed(self):
        self.raise_completed("".join(self.data))
    
    def __str__(self):
        if self.left:
            return "ReadOperation(fd=%i, to_read=%i)" % (self.fd, self.left)
        else:
            read = sum(len(chunk) for chunk in self.data)
            return "ReadOperation(fd=%i, read=%i)" % (self.fd, read)

class WriteOperation(IOOperation):
    def __init__(self, reactor, file, data, cont):
        super(WriteOperation, self).__init__(reactor)
        self.event = select.POLLOUT
        self.init_file(file)
        self.size = len(data)
        self.data = data
        self.left = len(data)
        self.cont = cont
    
    def complete(self):
        success, written = self.nonblock(os.write, (self.fd, self.data, ))
        if success and written > 0:
            self.data = self.data[written:]
            self.left -= written
            return self.left == 0
        else:
            return False
    
    def __str__(self):
        return "WriteOperation(fd=%i, size=%i)" % (self.fd, self.size)

class ConnectOperation(IOOperation):
    def __init__(self, reactor, nbsock, address, cont):
        super(ConnectOperation, self).__init__(reactor)
        self.fd = nbsock.fileno
        self.event = select.POLLOUT
        self.nbsock = nbsock
        self.address = address
        self.cont = cont

    def complete(self):
        success, result = self.nonblock(self.nbsock.socket.connect,
            (self.address, ), os.errno.EINPROGRESS)
        return success
    
    def completed(self):
        self.raise_completed((self.nbsock, self.address))
    
    def __str__(self):
        return "ConnectOperation(fd=%i, addr=%s)" % (self.fd, repr(self.address))

class AcceptOperation(IOOperation):
    def __init__(self, reactor, nbsock, cont):
        super(AcceptOperation, self).__init__(reactor)
        self.fd = nbsock.fileno
        self.event = select.POLLIN
        self.nbsock = nbsock
        self.conn = None
        self.address = None
        self.cont = cont
    
    def complete(self):
        success, result = self.nonblock(self.nbsock.socket.accept)
        if success:
            self.conn, self.address = result
        return success
    
    def completed(self):
        self.raise_completed((NonBlockingSocket(self.reactor, self.conn), self.address))
    
    def __str__(self):
        return "AcceptOperation(fd=%i)" % (self.fd)

class NonBlockingFile(object):
    """ File-like object that uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, fd):
        self.reactor = reactor
        self.fd = fd
    
    @property
    def fileno(self):
        return self.fd
    
    @classmethod
    def open(cls, reactor, file, mode=None):
        if mode == "w":
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        elif mode == "a":
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        elif mode == "r+":
            flags = os.O_RDWR
        elif mode == "w+":
            flags = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        elif mode == "a+":
            flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
        else:
            flags =  os.O_RDONLY
        fd = os.open(file, flags | os.O_NONBLOCK)
        return cls(reactor, fd)
    
    def beginRead(self, size):
        return _beginRead(self.reactor, self.fd, size)
    
    def beginWrite(self, data):
        return _beginWrite(self.reactor, self.fd, data)
    
    def read(self, size):
        return self.beginRead(size).result
    
    def write(self, data):
        self.beginWrite(data).wait()
    
    def close(self):
        if self.fd:
            os.close(self.fd)
            self.fd = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

class NonBlockingSocket(object):
    """ File-like wrapper for a socket. Uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, sock):
        self.reactor = reactor
        self.socket = sock
        sock.setblocking(0)
    
    @property
    def fileno(self):
        return self.socket.fileno()
    
    @classmethod
    def socket(cls, reactor, family, type, proto):
        sock = socket.socket(family, type, proto)
        return cls(reactor, sock)
    
    def bind(self, address):
        return self.socket.bind(address)
    
    def listen(self, backlog=1):
        return self.socket.listen(backlog)
    
    def beginConnect(self, address):
        cont = Future()
        op = ConnectOperation(self.reactor, self, address, cont)
        self.reactor.submit(op)
        return cont
    
    def beginAccept(self):
        cont = Future()
        op = AcceptOperation(self.reactor, self, cont)
        self.reactor.submit(op)
        return cont
    
    def beginRead(self, size):
        return _beginRead(self.reactor, self.socket.fileno(), size)
    
    def beginWrite(self, data):
        return _beginWrite(self.reactor, self.socket.fileno(), data)
    
    def shutdown(self, how):
        return self.socket.shutdown(how)
    
    def close(self):
        return self.socket.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()