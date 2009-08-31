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

# Support for poor man's exception chaining with Python 2.x
import sys
import traceback
from cStringIO import StringIO

__all__ = ["Future", "FutureFrozenError", "TaskError", "TaskFailedError", "TaskCanceledError",
           "Delegate", "BlockingQueue", "QueueClosedError", "asyncMethod", "threadedMethod"]

def asyncMethod(func):
    """
    Mark the function asynchronous. The last argument must be a future.
    
    An asynchronous function does not block. When the operation is completed,
    the caller is notified through the future object.
    
    The decoration makes the function synchronous if the future object is None,
    and also allows passing a callable instead of a future.
    """
    def wrapper(*args, **kw):
        if len(args) == 0:
            return func(*args, **kw)
        arg = args[-1]
        if arg is None:
            future = Future()
            newArgs = args[:-1] + (future, )
            func(*newArgs, **kw)
            return future.result
        elif hasattr(arg, "__call__"):
            newArgs = args[:-1] + (Future(arg), )
            return func(*newArgs, **kw)
        else:
            if not arg.pending:
                raise ValueError("The future object has been used already")
            return func(*args, **kw)
    return wrapper

def threadedMethod(func):
    """
    Mark the function threaded. This adds an argument to the function,
    to which a callable, a future or None can be passed.
    
    If the future object is None, the function is executed synchronously.
    Otherwise a thread is started, which executes the function and
    appropriately calls completed() with the result value or failed().
    """
    def wrapper(*args, **kw):
        if (len(args) == 0) or (args[-1] is None):
            return func(*args, **kw)
        args, last = args[:-1], args[-1]
        if last is None:
            return func(*args, **kw)
        else:
            if hasattr(last, "__call__"):
                last = Future(last)
            elif not last.pending:
                raise ValueError("The future object has been used already")
            args = (func, ) + args
            t = threading.Thread(target=last.run, args=args, kwargs=kw)
            t.daemon = True
            t.start()
    return wrapper

class Future(object):
    """
    Represents a task whose result will be known in the future.
    passSelf determines whether "self" should be passed to the callback or not.
    """
    def __init__(self, callback=None, passSelf=True):
        if passSelf and (callback is not None):
            # is the callback a bound function?
            if hasattr(callback, "__self__"):
                self.__callback = types.MethodType(lambda f: callback(f), self)
            else:
                self.__callback = types.MethodType(callback, self)
        else:
            self.__callback = callback
        self.__result = None
        self.__lock = threading.RLock()
        self.__wait = threading.Condition(self.__lock)
    
    @property
    def pending(self):
        """ Indicate whether the task is still active or if it is complete. """
        with self.__lock:
            return self.__result is None
    
    @property
    def result(self):
        """
        Access the result of the task. If it is not available yet, block until it is.
        May raise an exception if the task failed.
        """
        with self.__lock:
            while self.__result is None:
                self.__wait.wait()
            r = self.__result
            if isinstance(r, tuple):
                return r
            elif isinstance(r, BaseException):
                raise r
            else:
                raise StandardError("The task failed for an unknown reason")
    
    def wait(self):
        """
        Wait for the task to be completed. Does not raise an exception if the task fails.
        """
        with self.__lock:
            while self.__result is None:
                self.__wait.wait()
    
    def run(self, func, *args, **kw):
        """
        Invoke a function, the return value will be the result of the task.
        completed() is called on success, or failed() if an exception is raised.
        """
        try:
            result = func(*args, **kw)
        except:
            self.failed()
        else:
            self.completed(result)
    
    def _assignResult(self, result):
        """ Set the result and invoke the callback, if any. """
        callback = None
        with self.__lock:
            if self.__result is None:
                self.__result = result
                self.__wait.notifyAll()
                callback = self.__callback
            elif isinstance(self.__result, TaskCanceledError):
                raise TaskCanceledError(self.__result.tb)
            else:
                raise FutureFrozenError("The result of the task has already been set")
        
        # don't call the callback with the lock held
        if callback:
            callback()
    
    def completed(self, *args):
        """ Provide the result of the task. """
        self._assignResult(args)
    
    def failed(self, e=None):
        """ Indicate that the task failed, maybe because of an exception. """
        type, val, tb = sys.exc_info()
        if not e is None:
            if (not isinstance(e, BaseException)):
                raise TypeError("e should be either None or an exception")
            elif e is val:
                error = TaskFailedError(type, val, tb)
            else:
                tb = traceback.extract_stack()[:-1]
                error = TaskFailedError(e.__class__, e, tb)
        else:
            error = TaskFailedError(type, val, tb)
        self._assignResult(error)
    
    def cancel(self):
        """ Cancel the task, making it impossible to complete. """
        tb = traceback.extract_stack()[:-1]
        self._assignResult(TaskCanceledError(tb))
    
class FutureFrozenError(StandardError):
    """ Exception raised when one tries to call completed() or failed() twice on a future. """
    pass

class TaskError(StandardError):
    """ Base class for errors related to Future tasks. """
    pass

def format_exception(type, value, tb):
    """ Format just exception, just a traceback or both. Return a list of lines. """
    buffer = StringIO()
    if hasattr(tb, "tb_frame"):
        if (type is not None) and (value is not None):
            traceback.print_exception(type, value, tb, file=buffer)
        else:
            traceback.print_tb(tb, file=buffer)
    else:
        if tb is not None:
            for line in traceback.format_list(tb):
                buffer.write(line)
        if (type is not None) and (value is not None):
            for line in traceback.format_exception_only(type, value):
                buffer.write(line)
    buffer.seek(0)
    return buffer.readlines()

class TaskFailedError(TaskError):
    """ Holds information about an error that occured during the execution of a task."""
    def __init__(self, type, value, tb):
        self.type = type
        self.value = value
        self.tb = tb
    
    def __str__(self):
        # hack until Python 3 which supports chained exceptions
        lines = format_exception(self.type, self.value, self.tb)
        lines[-1] = lines[-1].rstrip("\n")
        desc = "|  ".join(lines)
        if len(desc):
            desc = "\n" + desc
        return "The task failed: %s" % desc

class TaskCanceledError(TaskError):
    """ The task was canceled before it could be completed. """
    def __init__(self, tb=None):
        self.tb = tb
    
    def __str__(self):
        lines = ["Traceback: \n"]
        lines.extend(format_exception(None, None, self.tb))
        lines[-1] = lines[-1].rstrip("\n")
        trace = "|".join(lines)
        return "The task was canceled before it could be completed. %s" % trace

class Delegate(object):
    ''' Handles a list of methods and functions
    Usage:
        d = Delegate([lock])
        d += function    # Add function to end of delegate list
        d(*args, **kw)   # Call all functions, returns a list of results
        d -= function    # Removes last matching function from list
    '''
    def __init__(self, lock=None):
        self.__lock = lock or threading.Lock()
        self.__delegates = []
    
    def __iadd__(self, callback):
        with self.__lock:
            self.__delegates.append(callback)
        return self
    
    def __isub__(self, callback):
        if callable(callback):
            with self.__lock:
                for i in range(len(self.__delegates) - 1, -1, -1):
                    if self.__delegates[i] == callback:
                        del self.__delegates[i]
                        return self
        return self
    
    def __call__(self, *args, **kw):
        # don't call the callbacks with the lock held, so need to copy them
        with self.__lock:
            callbacks = self.__delegates[:]
        return [callback(*args, **kw) for callback in callbacks]

class QueueClosedError(Exception):
    pass

class BlockingQueue(object):
    """ Blocking queue which can be used to pass objects between threads. """
    def __init__(self, size, open=True, lock=None):
        if lock is None:
            self.__lock = threading.Lock()
        else:
            self.__lock = lock
        self.__wait = threading.Condition(self.__lock)
        self.__size = size
        self.__count = 0
        if open:
            self.__list = []
        else:
            self.__list = None
        self.__closing = False
    
    def __iter__(self):
        """ Iterate over the items in the queue, calling get() until the queue is closed. """
        while True:
            yield self._iter_get()
    
    def _iter_get(self):
        try:
            return self.get()
        except QueueClosedError:
            raise StopIteration()
    
    def put(self, item):
        """ Wait until the queue is not full, and put the item at the end. """
        with self.__lock:
            self.__assertWrite()
            while self.__count == self.__size:
                self.__wait.wait()
                self.__assertWrite()
            self.__list.append(item)
            self.__count += 1
            self.__wait.notifyAll()
    
    def get(self):
        """ Wait until the queue is not empty, and return the first item. """
        with self.__lock:
            self.__assertRead()
            while self.__count == 0:
                self.__wait.wait()
                self.__assertRead()
            item = self.__list.pop(0)
            self.__count -= 1
            self.__wait.notifyAll()
        return item
    
    def __assertWrite(self):
        """ Ensure that is it allowed to insert items into the queue. """
        if (self.__list is None) or self.__closing:
            raise QueueClosedError()
    
    def __assertRead(self):
        """ Ensure that is it allowed to read items from the queue. """
        if (self.__list is None) or (self.__closing and (self.__count == 0)):
            raise QueueClosedError()
    
    def open(self):
        """ Create (or re-create) a closed queue, which will be empty. """
        with self.__lock:
            if self.__list is None:
                self.__count = 0
                self.__list = []
    
    def close(self, waitEmpty=False):
        """
        Close the queue, raising an exception on threads waiting for put or get to complete.
        
        If waitEmpty is true, then calling get() doesn't raise an exception as long
        as there are still items in the queue. In either case put() raises an exception.
        """
        with self.__lock:
            if waitEmpty:
                self.__closing = True
                while self.__count > 0:
                    self.__wait.wait()
                    if self.__list is None:
                        return
            if self.__list is not None:
                self.__count = 0
                self.__list = None
                self.__closing = False
                self.__wait.notifyAll()