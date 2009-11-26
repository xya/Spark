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
import select
import fcntl
import threading
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
        self.req_r, self.req_w = os.pipe()
        blocking_mode(self.req_r, False)
        blocking_mode(self.req_w, False)
    
    def register(self, file):
        """ Register the file to be used for asynchronous I/O operations. """
        if hasattr(file, "fileno"):
            fd = file.fileno()
        else:
            fd = file
        blocking_mode(fd, False)
    
    def read(self, file, size):
        cont = Future()
        op = ReadOperation(self, file, size, cont)
        self.submit(op)
        return cont
    
    def write(self, file, data):
        cont = Future()
        op = WriteOperation(self, file, data, cont)
        self.submit(op)
        return cont
    
    def connect(self, socket, address):
        cont = Future()
        op = ConnectOperation(self, socket, address, cont)
        self.submit(op)
        return cont
    
    def accept(self, socket):
        cont = Future()
        op = AcceptOperation(self, socket, cont)
        self.submit(op)
        return cont
    
    def callback(self, fun, *args, **kwargs):
        """ Submit a function to be called back on the reactor's thread. """
        op = InvokeOperation(self, fun, args, kwargs)
        self.submit(op)
    
    def launch_thread(self):
        """ Start a background I/O thread to run the reactor. """
        with self.lock:
            if self.active is False:
                self.active = True
                t = threading.Thread(target=self.eventLoop, name="I/O thread")
                t.daemon = True
                t.start()
                return True
            else:
                return False
    
    def run(self):
        """ Run the reactor on the current thread. """
        with self.lock:
            if self.active is False:
                self.active = True
            else:
                return
        self.eventLoop()
    
    def submit(self, op):
        """
        Submit an I/O request to be performed asynchronously.
        Requests are not processed before either run() or launch_thread() is called.
        """
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
        try:
            self.onClosed()
        except Exception:
            self.logger.exception("onClosed() failed")
    
    def eventLoop(self):
        self.poll = select.poll()
        self.queue.put(PipeReadOperation(self, self.req_r))
        self.empty_queue()
        try:
            while True:
                self.logger.log(LOG_VERBOSE, "Waiting for poll()")
                events = self.poll.poll()
                self.logger.log(LOG_VERBOSE, "Woke up from poll()")
                for fd, event in events:
                     self.perform_io(fd, event)
        except QueueClosedError:
            pass
        finally:
            self.cleanup()
    
    def empty_queue(self):
        for op in self.queue.iter_nowait():
            try:
                finished = op.complete()
            except:
                op.failed()
            else:
                if finished:
                    op.completed()
                else:
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
                try:
                    op.complete(event)
                except:
                    op.failed()
                else:
                    op.canceled()
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
                try:
                    finished = found.complete(event)
                except:
                    found.failed()
                else:
                    if finished:
                        self.remove_op(found)
                        found.completed()
    
    def remove_op(self, op):
        op_queue = self.pending[op.fd]
        op_queue.remove(op)
        if len(op_queue) == 0:
            self.poll.unregister(op.fd)
            del self.pending[op.fd]

class IOOperation(object):
    def __init__(self, reactor):
        self.reactor = reactor
        
    def complete(self, event=None):
        raise NotImplementedError()
    
    def init_file(self, file):
        """ Init the fd attribute. 'file' can either be a file or a file descriptor. """
        if hasattr(file, "fileno"):
            self.fd = file.fileno()
        else:
            self.fd = file
    
    def canceled(self):
        self.raise_canceled()
    
    def failed(self):
        self.raise_failed()
    
    def completed(self):
        self.raise_completed()
    
    def raise_completed(self, *args):
        self.reactor.logger.log(LOG_VERBOSE, "Completed operation %s" % str(self))
        try:
            self.cont.completed(*args)
        except:
            self.reactor.logger.error("Error in I/O completed() callback")
    
    def raise_failed(self, *args):
        self.reactor.logger.debug("Failed operation of %s" % str(self))
        try:
            self.cont.failed(*args)
        except:
            self.reactor.logger.error("Error in I/O failed() callback")
    
    def raise_canceled(self):
        self.reactor.logger.debug("Canceled operation of %s" % str(self))
        try:
            self.cont.cancel()
        except:
            self.reactor.logger.error("Error in I/O canceled() callback")
    
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
    def __init__(self, reactor, fun, args, kwargs):
        super(InvokeOperation, self).__init__(reactor)
        self.fun = fun
        self.args = args
        self.kwargs = kwargs
    
    def __str__(self):
        return "InvokeOperation(args=%s, kw=%s)" % (repr(self.args), repr(self.kwargs))
    
    def complete(self, event=None):
        return True
    
    def completed(self):
        self.reactor.logger.log(LOG_VERBOSE, "Completed operation %s" % str(self))
        try:
            self.fun(*self.args, **self.kwargs)
        except Exception as e:
            self.reactor.logger.error("Error in non-I/O callback: %s" % str(e))

class PipeReadOperation(IOOperation):
    def __init__(self, reactor, fd):
        super(PipeReadOperation, self).__init__(reactor)
        self.fd = fd
        self.event = select.POLLIN
    
    def complete(self, event=None):
        while True:
            success, data = self.nonblock(os.read, (self.fd, 64))
            if not success or (len(data) < 64):
                break
        self.reactor.empty_queue()
        return False
    
    def canceled(self):
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
    
    def complete(self, event=None):
        success, data = self.nonblock(os.read, (self.fd, self.left, ))
        if success:
            if len(data) > 0:
                self.data.append(data)
                self.left -= len(data)
                return self.left == 0
            else:
                # end of file or we got disconnected
                return True
        else:
            return False
    
    def canceled(self):
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
    
    def complete(self, event=None):
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
    def __init__(self, reactor, socket, address, cont):
        super(ConnectOperation, self).__init__(reactor)
        self.fd = socket.fileno()
        self.event = select.POLLOUT
        self.socket = socket
        self.address = address
        self.cont = cont

    def complete(self, event=None):
        success, result = self.nonblock(self.socket.connect, (self.address, ),
            os.errno.EINPROGRESS)
        return success
    
    def completed(self):
        self.raise_completed(self.socket, self.address)
    
    def __str__(self):
        return "ConnectOperation(fd=%i, addr=%s)" % (self.fd, repr(self.address))

class AcceptOperation(IOOperation):
    def __init__(self, reactor, socket, cont):
        super(AcceptOperation, self).__init__(reactor)
        self.fd = socket.fileno()
        self.event = select.POLLIN
        self.socket = socket
        self.conn = None
        self.address = None
        self.cont = cont
    
    def complete(self, event=None):
        success, result = self.nonblock(self.socket.accept)
        if success:
            self.conn, self.address = result
        return success
    
    def completed(self):
        self.raise_completed(self.conn, self.address)
    
    def __str__(self):
        return "AcceptOperation(fd=%i)" % (self.fd)