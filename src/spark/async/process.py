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
import logging
from spark.async import BlockingQueue, QueueClosedError

__all__ = ["all", "current", "run_main", "spawn", "send", "try_send", "receive", "try_receive",
           "ProcessExited", "ProcessKilled", "ProcessState", "ProcessEvent", "match"]

_lock = threading.RLock()
_processes = {}
_nextID = 1
_current = threading.local()

def all():
    """ Enumerates the IDs of all processes. """
    with _lock:
        return _processes.iter_keys()

def current():
    """ Return the ID of the currently executing process. """
    try:
        return _current.p.pid
    except AttributeError:
        return None

def logger():
    """ Return a logger for the currently executing process. """
    if hasattr(_current, "p"):
        p = _current.p
        if p.logger is None:
            p.logger = logging.getLogger(p.displayName())
        return p.logger
    else:
        return logging.getLogger()

def attach(name=None, queue=None):
    """ Associate the current thread with a PID and message queue. Return the PID. """
    current_pid = current()
    if current_pid is not None:
        raise Exception("This thread already has a PID")
    with _lock:
        pid = _new_id()
        p = _create_process(pid, name)
        if queue is not None:
            p.queue = queue
        _set_current_process(pid)
        p.thread = threading.current_thread()
    log = logger()
    log.info("Process attached.")
    return pid

def detach():
    """ Disassociate the current thread from its PID and message queue. """
    current_pid = current()
    if current_pid is None:
        raise Exception("The current thread has no PID")
    log = logger()
    log.info("Process detached.")
    with _lock:
        _remove_current_process(current_pid)

def spawn(fun, args=(), name=None):
    """ Create a new process and return its PID. """
    with _lock:
        pid = _new_id()
        p = _create_process(pid, name)
    def entry():
        with _lock:
            _set_current_process(pid)
        log = logger()
        log.info("Process started.")
        try:
            fun(*args)
        except ProcessKilled:
            log.info("Process killed.")
        except Exception:
            log.exception("An exception was raised by the process")
        else:
            log.info("Process stopped.")
        finally:
            with _lock:
                _remove_current_process(pid)
    p.thread = threading.Thread(target=entry)
    p.thread.daemon = True
    p.thread.start()
    return pid

def send(pid, m):
    """ Send a message to the specified process. """
    with _lock:
        try:
            p = _processes[pid]
            queue = p.queue
        except KeyError:
            raise Exception("Invalid PID")
    try:
        queue.put(m)
    except QueueClosedError:
        raise ProcessExited("Can't send a message to a stopped process (PID: %i)" % pid)

def try_send(pid, m):
    """ Send a message to the specified process. If the process exited, return False. """
    try:
        send(pid, m)
        return True
    except ProcessExited:
        return False

def receive():
    """ Retrieve a message from the current process' queue. """
    try:
        p = _current.p
    except NameError:
        raise Exception("The current thread has no PID")
    try:
        return p.queue.get()
    except QueueClosedError:
        raise ProcessKilled("The process got killed (PID: %i)" % p.pid)

def try_receive():
    """
    Retrieve a message from the current process' queue and return (True, message).
    If a message can't be retrieved now, return (False, None).
    """
    try:
        p = _current.p
    except NameError:
        raise Exception("The current thread has no PID")
    return p.queue.get_nowait()

def kill(pid, flushQueue=True):
    """ Kill the specified process by closing its message queue. Return False on error. """
    with _lock:
        try:
            p = _processes[pid]
            queue = p.queue
        except KeyError:
            return False
    logger().info("Killing process %i.", pid)
    queue.close(flushQueue)
    return True

def _new_id():
    global _nextID
    id = _nextID
    _nextID += 1
    return id

def _create_process(pid, name):
    p = Process(pid, name)
    _processes[pid] = p
    return p

def _set_current_process(pid):
    _current.p = _processes[pid]

def _remove_current_process(current_pid):
    p = _current.p
    p.queue.close()
    del _current.p
    #del _processes[current_pid]

class Process(object):
    def __init__(self, pid, name):
        self.pid = pid
        self.name = name
        self.queue = BlockingQueue(64)
        self.thread = None
        self.logger = None
    
    def displayName(self):
        if self.name:
            return "%s-%i" % (self.name, self.pid)
        else:
            return "process-%i" % self.pid

class ProcessExited(Exception):
    pass

class ProcessKilled(Exception):
    pass

class ProcessState(object):
    """ Object that can be used to store a process' state (which should not be shared across threads). """
    pass

class ProcessEvent(object):
    """ Event which can be suscribed by other processes. """
    def __init__(self, lock=None):
        self.__lock = lock or threading.Lock()
        self.__suscribers = set()
    
    def suscribe(self, pid=None):
        """ Suscribe a process to start receiving notifications of this event. """
        if not pid:
            pid = current()
            if not pid:
                raise Exception("The current thread has no PID")
        with self.__lock:
            self.__suscribers.add(pid)
    
    def unsuscribe(self, pid=None):
        """ Unsuscribe a process to stop receiving notifications of this event. """
        if not pid:
            pid = current()
            if not pid:
                raise Exception("The current thread has no PID")
        with self.__lock:
            self.__suscribers.remove(pid)

    def __call__(self, m):
        """ Send a message to all suscribed processes. """
        # don't send messages with the lock held, so need to copy the suscribers
        with self.__lock:
            suscribers = self.__suscribers.copy()
        for pid in suscribers:
            try:
                send(pid, m)
            except Exception:
                pass