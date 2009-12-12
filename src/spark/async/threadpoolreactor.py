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
import threading
import socket
import logging
from spark.async import Future, BlockingQueue, QueueClosedError, Delegate, TaskFailedError
from spark.async.aio import Reactor

__all__ = ["ThreadPoolReactor"]

LOG_VERBOSE = 5

# (REQ_INVOKE, (op, ))
REQ_INVOKE = 0
# (REQ_IO_CALL, (op, ))
REQ_IO_CALL = 1
# (RESP_RESULT, (op, workerID, result))
RESP_IO_RESULT = 2
# (RESP_IO_EXCEPTION, (op, workerID, type, val, traceback))
RESP_IO_EXCEPTION = 3

class ThreadPoolReactor(Reactor):
    def __init__(self, name=None, lock=None):
        self.logger = logging.getLogger(name)
        if lock:
            self.lock = lock
        else:
            self.lock = threading.RLock()
        self.reactorQueue = BlockingQueue(64, lock=self.lock)
        self.idleQueue = BlockingQueue(64, lock=self.lock)
        self.workers = []
        self.onClosed = Delegate(self.lock)
        self.thread = None
    
    def socket(self, family, type, proto):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        return ThreadPoolSocket.socket(self, family, type, proto)
    
    def open(self, path, mode=None):
        """ Open a file that uses the reactor to do asynchronous I/O. """
        return ThreadPoolFile.open(self, path, mode)
    
    def pipe(self):
        """ Create a pipe that uses the reactor to do asynchronous I/O. """
        r, w = os.pipe()
        return ThreadPoolFile(self, r), ThreadPoolFile(self, w)
    
    def send(self, fun, *args, **kwargs):
        """ Invoke a callable on the reactor's thread and return its result through a future. """
        if fun is None:
            raise TypeError("The callable must not be None")
        cont = Future()
        op = Operation(self, cont, "Invoke", fun, *args, **kwargs)
        self.submit(REQ_INVOKE, op)
        return cont
    
    def post(self, fun, *args, **kwargs):
        """ Submit a callable to be invoked on the reactor's thread later. """
        if fun is None:
            raise TypeError("The callable must not be None")
        op = Operation(self, None, "Invoke", fun, *args, **kwargs)
        self.submit(REQ_INVOKE, op)
    
    def launch_thread(self):
        """ Start a background I/O thread to run the reactor. """
        with self.lock:
            if self.thread is None:
                self.thread = threading.Thread(target=self.eventLoop, name="I/O event thread")
                self.thread.daemon = True
                self.thread.start()
                return True
            else:
                return False
    
    def run(self):
        """ Run the reactor on the current thread. """
        with self.lock:
            if self.thread is None:
                self.active = True
                self.thread = threading.currentThread()
            else:
                return
        self.eventLoop()
    
    def submit(self, type, *args):
        """
        Submit an I/O request to be performed asynchronously. If submit() is
        called on the reactor's thread the operation will be started immediatly;
        otherwise it will be started when it gets dequeued by the reactor's thread.
        """
        self.logger.log(LOG_VERBOSE, "Submitting operation %s" % str(args[0]))
        self.reactorQueue.put((type, args))
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        self.reactorQueue.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()
    
    def cleanup(self):
        self.logger.debug("Reactor shutting down")
        self.reactorQueue.close()
        self.idleQueue.close()
        with self.lock:
            for worker in self.workers:
                worker.stop()
            self.workers = []
            self.thread = None
        try:
            self.onClosed()
        except Exception:
            self.logger.exception("onClosed() failed")
    
    def eventLoop(self):
        try:
            logging = self.logger.isEnabledFor(LOG_VERBOSE)
            while True:
                type, req = self.reactorQueue.get()
                if type == REQ_INVOKE:
                    op = req[0]
                    try:
                        result = op()
                    except Exception:
                        op.failed("reactor")
                    else:
                        op.completed("reactor", result)
                elif type == REQ_IO_CALL:
                    op = req[0]
                    success, worker = self.idleQueue.get_nowait()
                    if not success:
                        self.spawnWorker()
                        worker = self.idleQueue.get()
                    worker.submit(op)
                elif type == RESP_IO_RESULT:
                    op, workerID, result = req
                    op.completed(workerID, result)
                elif type == RESP_IO_EXCEPTION:
                    op, workerID, type, value, tb = req
                    op.failed(workerID, TaskFailedError(type, value, tb))
        except QueueClosedError:
            pass
        finally:
            self.cleanup()
    
    def spawnWorker(self):
        workerQueue = BlockingQueue(4)
        worker = WorkerThread(self.logger, workerQueue, self.reactorQueue, self.idleQueue)
        with self.lock:
            self.workers.append(worker)

class WorkerThread(object):
    def __init__(self, logger, workQueue, resultQueue, idleQueue):
        self.logger = logger
        self.workQueue = workQueue
        self.resultQueue = resultQueue
        self.idleQueue = idleQueue
        self.id = hex(id(self))
        self.thread = threading.Thread(target=self.workerLoop, name="I/O worker")
        self.thread.daemon = True
        self.thread.start()
    
    def submit(self, op):
        self.workQueue.put(op)
    
    def stop(self):
        self.workQueue.close()
    
    def workerLoop(self):
        self.logger.info("Worker %s started" % self.id)
        try:
            self.idleQueue.put(self)
            while True:
                op = self.workQueue.get()
                try:
                    result = op()
                except Exception:
                    response = (RESP_IO_EXCEPTION, (op, self.id) + sys.exc_info())
                else:
                    response = (RESP_IO_RESULT, (op, self.id, result))
                # join the idle queue before submitting the result to avoid spawning extra workers
                self.idleQueue.put(self)
                self.resultQueue.put(response)
        except QueueClosedError:
            pass
        except Exception:
            self.logger.exception("Error in worker thread")
        self.logger.info("Worker %s stopped" % self.id)

class Operation(object):
    def __init__(self, reactor, cont, type, fun, *args, **kwargs):
        self.reactor = reactor
        self.cont = cont
        self.type = type
        self.fun = fun
        self.args = args
        self.kwargs = kwargs
        
    def __str__(self):
        args = [repr(arg) for arg in self.args]
        for key, val in self.kwargs:
            args.append("%s=%s" % (key, repr(val)))
        return "%s(%s)" % (self.type, ", ".join(args))
    
    def __call__(self):
        return self.fun(*self.args, **self.kwargs)
    
    def completed(self, workerID, result=None):
        if self.reactor.logger.isEnabledFor(LOG_VERBOSE):
            self.reactor.logger.log(LOG_VERBOSE, "[Worker %s] Completed operation %s" % (workerID, str(self)))
        if self.cont is not None:
            try:
                self.cont.completed(result)
            except Exception:
                self.reactor.logger.exception("Error in completed() callback")
    
    def failed(self, workerID, exc=None):
        self.reactor.logger.debug("[Worker %s] Failed operation of %s" % (workerID, str(self)))
        if self.cont is not None:
            try:
                self.cont.failed(exc)
            except Exception:
                self.reactor.logger.exception("Error in failed() callback")
    
    def canceled(self):
        self.reactor.logger.debug("Canceled operation of %s" % str(self))
        if self.cont is not None:
            try:
                self.cont.cancel()
            except Exception:
                self.reactor.logger.exception("Error in canceled() callback")

class WriteOperation(Operation):
    def __init__(self, reactor, cont, type, fun, *args, **kwargs):
        super(WriteOperation, self).__init__(reactor, cont, type, fun, *args, **kwargs)
    
    def __str__(self):
        if len(self.args) == 1:
            return "WriteOperation(%i)" % len(self.args[0])
        elif len(self.args) == 2:
            return "WriteOperation(%i, %i)" % (self.args[0], len(self.args[1]))
        else:
            return "WriteOperation()"

class ThreadPoolFile(object):
    """ File-like object that uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, fd):
        self.reactor = reactor
        self.fd = fd
    
    @property
    def fileno(self):
        return self.fd
    
    @classmethod
    def open(cls, reactor, path, mode=None):
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
        fd = os.open(path, flags | os.O_NONBLOCK, 0o666)
        return cls(reactor, fd)
    
    def beginRead(self, size):
        cont = Future()
        op = Operation(self.reactor, cont, "Read", os.read, self.fd, size)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont
    
    def beginWrite(self, data):
        cont = Future()
        op = WriteOperation(self.reactor, cont, "Write", os.write, self.fd, data)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont

    def read(self, size):
        return self.beginRead(size).result
    
    def write(self, data):
        self.beginWrite(data).wait()
    
    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

class ThreadPoolSocket(object):
    """ File-like wrapper for a socket. Uses a reactor to perform asynchronous I/O. """
    def __init__(self, reactor, sock):
        self.reactor = reactor
        self.socket = sock
    
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
        op = Operation(self.reactor, cont, "Connect", self.socket.connect, address)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont
    
    def beginAccept(self):
        cont = Future()
        def doAccept():
            conn, remoteAddr = self.socket.accept()
            return ThreadPoolSocket(self.reactor, conn), remoteAddr
        op = Operation(self.reactor, cont, "Accept", doAccept)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont
    
    def beginRead(self, size):
        cont = Future()
        op = Operation(self.reactor, cont, "Read", self.socket.recv, size)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont
    
    def beginWrite(self, data):
        cont = Future()
        op = WriteOperation(self.reactor, cont, "Write", self.socket.send, data)
        self.reactor.submit(REQ_IO_CALL, op)
        return cont
    
    def shutdown(self, how):
        return self.socket.shutdown(how)
    
    def close(self):
        return self.socket.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        self.close()

# register the reactor
Reactor.addType(ThreadPoolReactor)