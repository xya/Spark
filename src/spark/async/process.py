# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Pierre-André Saulais <pasaulais@free.fr>
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

""" Interface that allows the use of Erlang-like processes that can send messages to each other. """

import threading
from spark.async import BlockingQueue

__all__ = ["all", "current", "run_main", "spawn", "send", "receive"]

_lock = threading.RLock()
_processes = {}
_main = None
_nextID = 0

def all():
    """ Enumerates the IDs of all processes. """
    with _lock:
        return _processes.iter_keys()

def current():
    """ Return the ID of the currently executing process. """
    try:
        return threading.local.pid
    except NameError:
        return None

def run_main(fun, *args, **kargs):
    """ Executes a callable as the main process. """
    with _lock:
        if _main is not None:
            raise Exception("A main process is already executing")
        _main = _new_id()
        _create_process(_main, "Main")
        _set_current_process(_main)
    fun(*args, **kargs)

def spawn(name, fun, *args, **kargs):
    """ Create a new process and return its ID. """
    with _lock:
        if _main is None:
            raise Exception("You must call 'run_main' first")
        pid = _new_id()
        p = _create_process(pid, name)
    def entry():
        with _lock:
            _set_current_process(pid)
        try:
            fun(*args, **kargs)
        finally:
            with _lock:
                del _processes[pid]
    p.thread = threading.Thread(target=entry)
    p.thread.daemon = False
    p.thread.start()

def send(pid, m):
    """ Send a message to the specified process. """
    with _lock:
        try:
            p = _processes[pid]
            queue = p.queue
        except KeyError:
            raise Exception("Invalid PID")
    queue.put(m)

def receive():
    """ Retrieve a message from the current process' queue. """
    try:
        queue = threading.local.queue
    except NameError:
        raise Exception("The current thread has no PID")
    return queue.get()

def _new_id():
    id = _nextID
    _nextID += 1
    return 1

def _create_process(pid, name):
    p = Process(pid, name)
    _processes[pid] = p
    return p

def _set_current_process(pid):
    p = _processes[pid]
    threading.local.pid = pid
    threading.local.queue = p.queue

class Process(object):
    def __init__(self, pid, name):
        self.pid = pid
        self.name = name
        self.queue = BlockingQueue(64)
        self.thread = None