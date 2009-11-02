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
           "Delegate", "BlockingQueue", "QueueClosedError", "threadedMethod", "coroutine"]

def threadedMethod(func):
    """
    When the function is called a thread is started, which executes the function
    and appropriately calls completed() with the result values or failed().
    """
    def wrapper(*args, **kw):
        cont = Future()
        newArgs = (func, ) + args
        t = threading.Thread(target=cont.run, args=newArgs, kwargs=kw)
        t.daemon = True
        t.start()
        return cont
    return wrapper

def coroutine(func):
    """
    Wrap a generator function to act as a coroutine. The new function creates a
    future and executes the generator until it yields. The future is then returned.
    """
    def wrapper(*args, **kw):
        cont = Future()
        cont.run_coroutine(func(*args, **kw))
        return cont
    return wrapper

class Future(object):
    """
    Represents a task whose result will be known in the future.
    """
    def __init__(self):
        self.__callback = None
        self.__args = None
        self.__result = None
        self.__lock = threading.RLock()
        self.__wait = threading.Condition(self.__lock)
    
    @classmethod
    def done(cls, *args):
        """
        Create a future whose operation is already done (e.g. completed synchronously without blocking).
        """
        f = cls()
        f.completed(*args)
        return f
    
    @classmethod
    def error(cls, e=None):
        """
        Create a future whose operation has already failed (e.g. failed synchronously without blocking).
        """
        f = cls()
        f.failed(e)
        return f
    
    """
    Invoke the callable or Future when the operation completes. If it was completed before, it is called before returning.
    The first argument of the function will be the Future, but optional args can be passed.
    Return True if the operation is complete, or False otherwise.
    """
    def after(self, continuation, *args):
        callback = self._makeCallback(continuation)
        with self.__lock:
            result = self.__result
            if result is None:
                if self.__callback is None:
                    self.__callback = callback
                    self.__args = args
                else:
                    raise Exception("The continuation has already been set")
        self._invoke(result, callback, args)
        return result is not None
    
    @property
    def pending(self):
        """ Indicate whether the task is still active or if it is complete. """
        with self.__lock:
            return self.__result is None
        
    def wait(self, timeout=None):
        """
        Wait for the task to be completed and return the results of the task.
        This will raise an exception if the task failed or was canceled.
        """
        with self.__lock:
            while self.__result is None:
                if timeout is not None:
                    threading.Timer(timeout, self._interrupt_wait).start()
                self.__wait.wait()
                if (timeout is not None) and (self.__result is None):
                    raise WaitTimeoutError("The task didn't complete within the specified duration")
            r = self.__result
            if isinstance(r, tuple):
                return r
            elif isinstance(r, BaseException):
                raise r
            else:
                raise StandardError("The task failed for an unknown reason")
    
    def _interrupt_wait(self):
        """ Wake up the threads waiting for the results when the timeout is elapsed """
        with self.__lock:
            if self.__result is None:
                self.__wait.notifyAll()
    
    @property
    def results(self):
        """
        Access the results of the task. If no result is available yet, block until there are.
        May raise an exception if the task failed or was canceled.
        """
        return self.wait()   
    
    @property
    def result(self):
        """ Convenience property for accessing the first element of result. See results. """
        results = self.results
        if len(results) >= 1:
            return results[0]
        else:
            return None
    
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
        args = None
        with self.__lock:
            if self.__result is None:
                self.__result = result
                self.__wait.notifyAll()
                callback = self.__callback
                args = self.__args
            elif isinstance(self.__result, TaskCanceledError):
                raise TaskCanceledError(self.__result.tb)
            else:
                raise FutureFrozenError("The result of the task has already been set")
        
        # don't invoke the callback with the lock held
        self._invoke(result, callback, args)
    
    def _invoke(self, result, callback, args):
        if hasattr(callback, "__call__"):
            if result is not None:
                callback(*args)
        elif isinstance(callback, Future):
            if isinstance(result, tuple):
                callback.completed(*args)
            elif isinstance(result, BaseException):
                callback.failed()
    
    def _makeCallback(self, continuation):
        if hasattr(continuation, "__call__"):
            # bound function?
            if hasattr(continuation, "__self__"):
                return types.MethodType(lambda f, *args: continuation(f, *args), self)
            else:
                return types.MethodType(continuation, self)
        if isinstance(continuation, Future):
            return continuation
        else:
            raise ValueError("'continuation' should be a callable or a Future")
    
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
    
    def fork(self, completeCont, failCont, *args):
        """ Run one of two continuations, depending on the success of the operation. """
        def handler(prev):
            try:
                results = prev.results + args
            except:
                if hasattr(failCont, "failed"):
                    failCont.failed()
                elif hasattr(failCont, "__call__"):
                    failCont(*args)
            else:
                if hasattr(completeCont, "completed"):
                    completeCont.completed(*results)
                elif hasattr(completeCont, "__call__"):
                    completeCont(*results)
        self.after(handler)
    
    def run_coroutine(self, coroutine):
        """
        Execute a coroutine, which returns futures through 'yield'. When the
        future's task is completed, the result is passed to the coroutine.
        If the future's task fails, the exception is raised in the coroutine.
        """
        if not isinstance(coroutine, types.GeneratorType):
            raise TypeError("'coroutine' should be a generator")
        self._coroutine_send(coroutine, None)
    
    def _coroutine_send(self, coroutine, value):
        try:
            result = coroutine.send(value)
        except StopIteration:
            # the coroutine exited
            self.completed()
        except:
            # the coroutine raised an exception
            self.failed()
        else:
            # the coroutine yielded something
            self._coroutine_yielded(coroutine, result)
    
    def _coroutine_yielded(self, coroutine, result):
        if isinstance(result, Future):
            result.after(self._coroutine_task_completed, coroutine)
        elif result is None:
            self.completed()
        else:
            self.completed(result)
    
    def _coroutine_task_completed(self, prev, coroutine):
        try:
            result = prev.results
        except:
            # the task failed, propagate the exception to the coroutine
            type, val = sys.exc_info()[0:2]
            try:
                result = coroutine.throw(type, val)
            except StopIteration:
                # the coroutine handled the exception and exited
                self.completed()
            except:
                # the coroutine didn't handle the exception
                self.failed()
            else:
                # the coroutine yielded something
                self._coroutine_yielded(coroutine, result)
        else:
            # the task succeeded, send the result to the coroutine
            if len(result) == 0:
                result = None
            elif len(result) == 1:
                result = result[0]
            self._coroutine_send(coroutine, result)

class FutureFrozenError(StandardError):
    """ Exception raised when one tries to call completed() or failed() twice on a future. """
    pass

class WaitTimeoutError(StandardError):
    """ Exception raised when the timeout for wait() elapsed and the task isn't finished. """
    pass

class TaskError(StandardError):
    """ Base class for errors related to Future tasks. """
    pass

def format_exception(type, value, tb):
    """ Format just exception, just a traceback or both. Return a list of lines. """
    buffer = StringIO()
    if tb is not None:
        if hasattr(tb, "tb_frame"):
            tb = traceback.extract_tb(tb)
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
    
    def inner(self):
        """ Return the very first exception of a chain. """
        type, val, tb = self.type, self.value, self.tb
        while val is not None:
            if hasattr(val, "type") and hasattr(val, "value") and hasattr(val, "tb"):
                type, val, tb = val.type, val.value, val.tb
            else:
                break
        return type, val, tb

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

def _iter_wrap(func):
    def wrapper(*args):
        try:
            return func(*args)
        except QueueClosedError:
            raise StopIteration()
    return wrapper

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
    
    def iter_nowait(self):
        """ Iterate over the items in the queue, calling get() until the queue is empty. """
        success, item = self._iter_get_nowait()
        while success:
            yield item
            success, item = self._iter_get_nowait()
    
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
    
    _iter_get = _iter_wrap(get)
    
    def get_nowait(self):
        """ If the queue is not empty, return (True, <first item>). Otherwise return (False, None). """
        if self.__lock.acquire(0):
            try:
                self.__assertRead()
                if self.__count > 0:
                    item = self.__list.pop(0)
                    self.__count -= 1
                    self.__wait.notifyAll()
                    return (True, item)
                else:
                    return (False, None)
            finally:
                self.__lock.release()
    
    _iter_get_nowait = _iter_wrap(get_nowait)
    
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