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

class Future(object):
    """
    Represents a task whose result will be known in the future.
    passSelf determines whether "self" should be passed to the callback or not.
    """
    def __init__(self, callback=None, passSelf=True):
        if passSelf and (callback is not None):
            # is the callback a bound function?
            if hasattr(callback, "__self__"):
                self._callback = types.MethodType(lambda f: callback(f), self)
            else:
                self._callback = types.MethodType(callback, self)
        else:
            self._callback = callback
        self._result = None
        self._lock = threading.RLock()
        self._wait = threading.Condition(self._lock)
    
    @property
    def pending(self):
        """ Indicate whether the task is still active or if it is complete. """
        with self._lock:
            return self._result is None
    
    @property
    def result(self):
        """
        Access the result of the task. If it is not available yet, block until it is.
        May raise an exception if the task failed.
        """
        with self._lock:
            while self._result is None:
                self._wait.wait()
            r = self._result
            if isinstance(r, tuple):
                return r
            elif isinstance(r, bool):
                raise StandardError("The task failed for an unknown reason")
            else:
                raise r
    
    def completed(self, *args):
        """ Provide the result of the task. """
        callback = None
        with self._lock:
            if self._result is None:
                self._result = args
                self._wait.notifyAll()
                callback = self._callback
            else:
                raise StandardError("The result of the task has already been set")
        
        # don't call the callback with the lock held
        if callback:
            callback()
    
    def failed(self, e=None):
        """ Indicate that the task failed, maybe because of an exception. """
        if (e is not None) and (not isinstance(e, BaseException)):
            raise TypeError("e should be either None or an exception")
            
        callback = None
        with self._lock:
            if self._result is None:
                if e is None:
                    self._result = False
                else:
                    self._result = e
                self._wait.notifyAll()
                callback = self._callback
            else:
                raise StandardError("The result of the task has already been set")
        
        # don't call the callback with the lock held
        if callback:
            callback()