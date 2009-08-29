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

__all__ = ["asyncMethod", "Future", "FutureFrozenError", "TaskError", "Delegate"]

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
    
    def run(self, func, *args):
        """
        Invoke a function, the return value will be the result of the task.
        completed() is called on success, or failed() if an exception is raised.
        """
        try:
            result = func(*args)
        except:
            self.failed()
        else:
            self.completed(result)
    
    def completed(self, *args):
        """ Provide the result of the task. """
        callback = None
        with self.__lock:
            if self.__result is None:
                self.__result = args
                self.__wait.notifyAll()
                callback = self.__callback
            else:
                raise FutureFrozenError("The result of the task has already been set")
        
        # don't call the callback with the lock held
        if callback:
            callback()
    
    def failed(self, e=None):
        """ Indicate that the task failed, maybe because of an exception. """
        type, val, tb = sys.exc_info()
        if not e is None:
            if (not isinstance(e, BaseException)):
                raise TypeError("e should be either None or an exception")
            elif e is val:
                error = TaskError(type, val, tb)
            else:
                error = TaskError(e.__class__, val, None)
        else:
            error = TaskError(type, val, tb)
        
        callback = None
        with self.__lock:
            if self.__result is None:
                self.__result = error
                self.__wait.notifyAll()
                callback = self.__callback
            else:
                raise FutureFrozenError("The result of the task has already been set")
        
        # don't call the callback with the lock held
        if callback:
            callback()

class FutureFrozenError(StandardError):
    """ Exception raised when one tries to call completed() or failed() twice on a future. """
    pass

class TaskError(StandardError):
    """ Holds information about an error that occured during the execution of a task."""
    def __init__(self, type, value, tb):
        self.type = type
        self.value = value
        self.tb = tb
    
    def __str__(self):
        # hack until Python 3 which supports chained exceptions        
        if not self.tb is None:
            buffer = StringIO()
            buffer.write("\n")
            traceback.print_exception(self.type, self.value, self.tb, file=buffer)
            buffer.seek(0)
            lines = buffer.readlines()
            lines[-1] = lines[-1].rstrip("\n")
            desc = "|    ".join(lines)
        else:
            desc = str(r.value)
        return "The task failed: %s" % desc

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