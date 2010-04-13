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

import threading

__all__ = ["BlockingQueue", "QueueClosedError"]

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
        """ Iterate over the items in the queue, calling get() until the queue is empty or busy. """
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
        else:
            return (False, None)
    
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
        Return true if the queue was still open when close() was called, False otherwise.
        
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
                return True
            else:
                return False