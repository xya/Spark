import sys
import os
import select
import fcntl
import threading
import traceback
from async import Future, BlockingQueue, QueueClosedError

__all__ = ["blocking_mode", "IOReactor"]

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

def acceptCallable(func):
    """ Decorator which converts a callable to a future, when it is the last argument to the function. """
    def wrapper(*args, **kw):
        if (len(args) > 0) and hasattr(args[-1], "__call__"):
            args = args[:-1] + (Future(args[-1]), )
        return func(*args, **kw)
    return wrapper

class IOReactor(object):    
    def __init__(self):
        self.lock = threading.RLock()
        self.queue = BlockingQueue(64, lock=self.lock)
        self.pending = {}
        self.active = False
        self.req_r, self.req_w = os.pipe()
        blocking_mode(self.req_r, False)
        blocking_mode(self.req_w, False)
    
    @acceptCallable
    def begin_read(self, file, size, future):
        op = ReadOperation(file, size, future)
        self.submit(op)
    
    @acceptCallable
    def begin_write(self, file, data, future):
        op = WriteOperation(file, data, future)
        self.submit(op)
    
    @acceptCallable
    def begin_connect(self, socket, address, future):
        op = ConnectOperation(socket, address, future)
        self.submit(op)
    
    @acceptCallable
    def begin_accept(self, socket, future):
        op = AcceptOperation(socket, future)
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
    
    def run(self, future=None):
        """
        Run the reactor on the current thread, optionally signaling the future
        or calling back the callable when the event loop is entered.
        """
        with self.lock:
            if self.active is False:
                self.active = True
                if future:
                    if hasattr(future, "__call__"):
                        future = Future(future)
                    self.submit(NoOperation(future, self))
        self.eventLoop()
    
    def submit(self, op):
        """
        Submit an I/O request to be performed asynchronously.
        Requests are not processed before either run() or launch_thread() is called.
        """
        self.queue.put(op)
        os.write(self.req_w, '\0')
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        with self.lock:
            if self.req_w is not None:
                os.close(self.req_w)
                self.req_w = None
        self.queue.close()
    
    def cleanup(self):
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
    
    def eventLoop(self):
        self.poll = select.poll()
        self.queue.put(PipeReadOperation(self.req_r, self))
        self.empty_queue()
        try:
            while True:
                events = self.poll.poll()
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
        if hangup or error:
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
    def complete(self, event=None):
        raise NotImplementedError()
    
    def canceled(self):
        self.future_canceled()
    
    def failed(self):
        self.future_failed()
    
    def completed(self):
        self.future_completed()
    
    def future_completed(self, *args):
        try:
            self.future.completed(*args)
        except:
            traceback.print_exc()
    
    def future_failed(self, *args):
        try:
            self.future.failed(*args)
        except:
            traceback.print_exc()
    
    def future_canceled(self):
        try:
            self.future.cancel()
        except:
            traceback.print_exc()
    
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

class NoOperation(IOOperation):
    def __init__(self, future, reactor):
        self.future = future
        self.reactor = reactor
    
    def complete(self, event=None):
        return True
    
    def completed(self):
        self.future_completed(self.reactor)

class PipeReadOperation(IOOperation):
    def __init__(self, fd, reactor):
        self.fd = fd
        self.event = select.POLLIN
        self.reactor = reactor
    
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
    def __init__(self, file, size, future):
        self.fd = file.fileno()
        self.event = select.POLLIN
        self.file = file
        self.data = []
        self.left = size
        self.future = future
    
    def complete(self, event=None):
        success, data = self.nonblock(self.file.read, (self.left, ))
        if success and (len(data) > 0):
            self.data.append(data)
            self.left -= len(data)
            return self.left == 0
        else:
            return False
    
    def canceled(self):
        self.future_completed("")
        
    def completed(self):
        self.future_completed("".join(self.data))

class WriteOperation(IOOperation):
    def __init__(self, file, data, future):
        self.fd = file.fileno()
        self.event = select.POLLOUT
        self.file = file
        self.data = data
        self.left = len(data)
        self.future = future
    
    def complete(self, event=None):
        written = self.file.write(self.data)
        self.data = self.data[written:]
        self.left -= written
        return self.left == 0

class ConnectOperation(IOOperation):
    def __init__(self, socket, address, future):
        self.fd = socket.fileno()
        self.event = select.POLLOUT
        self.socket = socket
        self.address = address
        self.future = future

    def complete(self, event=None):
        success, result = self.nonblock(self.socket.connect, (self.address, ),
            os.errno.EINPROGRESS)
        return success
    
    def completed(self):
        self.future_completed(self.address)

class AcceptOperation(IOOperation):
    def __init__(self, socket, future):
        self.fd = socket.fileno()
        self.event = select.POLLIN
        self.socket = socket
        self.conn = None
        self.address = None
        self.future = future
    
    def complete(self, event=None):
        success, result = self.nonblock(self.socket.accept)
        if success:
            self.conn, self.address = result
        return success
    
    def completed(self):
        self.future_completed(self.conn, self.address)