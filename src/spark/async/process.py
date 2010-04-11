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

from collections import Sequence, Mapping
import threading
import logging
from spark.async.queue import BlockingQueue, QueueClosedError

__all__ = ["Process", "ProcessState", "ProcessRunner",
           "ProcessNotifier", "Command", "Event", "EventSender", "match", "MessageMatcher",
           "ProcessExited", "ProcessKilled"]

class Process(object):
    """ A process can execute callables and communicate using messages. """
    _lock = threading.RLock()
    _processes = {}
    _nextID = 1
    _current = threading.local()
    
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

    @classmethod
    def all(cls):
        """ Enumerates the IDs of all processes. """
        with cls._lock:
            return cls._processes.iter_keys()
    
    @classmethod
    def current(cls):
        """ Return the ID of the currently executing process. """
        try:
            return cls._current.p.pid
        except AttributeError:
            return None
    
    @classmethod
    def logger(cls):
        """ Return a logger for the currently executing process. """
        if hasattr(cls._current, "p"):
            p = cls._current.p
            if p.logger is None:
                p.logger = logging.getLogger(p.displayName())
            return p.logger
        else:
            return logging.getLogger()
    
    @classmethod
    def attach(cls, name=None, queue=None):
        """ Associate the current thread with a PID and message queue. Return the PID. """
        current_pid = cls.current()
        if current_pid is not None:
            raise Exception("This thread already has a PID")
        with cls._lock:
            pid = cls._new_id()
            p = cls._create_process(pid, name)
            if queue is not None:
                p.queue = queue
            cls._set_current_process(pid)
            p.thread = threading.current_thread()
        log = cls.logger()
        log.info("Process attached.")
        return pid
    
    @classmethod
    def detach(cls):
        """ Disassociate the current thread from its PID and message queue. """
        current_pid = cls.current()
        if current_pid is None:
            raise Exception("The current thread has no PID")
        log = cls.logger()
        log.info("Process detached.")
        with cls._lock:
            cls._remove_current_process(current_pid)
    
    @classmethod
    def spawn(cls, fun, args=(), name=None):
        """ Create a new process and return its PID. """
        with cls._lock:
            pid = cls._new_id()
            p = cls._create_process(pid, name)
        def entry():
            with cls._lock:
                cls._set_current_process(pid)
            log = cls.logger()
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
                with cls._lock:
                    cls._remove_current_process(pid)
        p.thread = threading.Thread(target=entry)
        p.thread.daemon = True
        p.thread.start()
        return pid
    
    @classmethod
    def send(cls, pid, m):
        """ Send a message to the specified process. """
        pid = cls._to_pid(pid)
        with cls._lock:
            try:
                p = cls._processes[pid]
                queue = p.queue
            except KeyError:
                raise Exception("Invalid PID")
        try:
            queue.put(m)
        except QueueClosedError:
            raise ProcessExited("Can't send a message to a stopped process (PID: %i)" % pid)
    
    @classmethod
    def try_send(cls, pid, m):
        """ Send a message to the specified process. If the process exited, return False. """
        pid = cls._to_pid(pid)
        try:
            cls.send(pid, m)
            return True
        except ProcessExited:
            return False
    
    @classmethod
    def receive(cls):
        """ Retrieve a message from the current process' queue. """
        try:
            p = cls._current.p
        except NameError:
            raise Exception("The current thread has no PID")
        try:
            return p.queue.get()
        except QueueClosedError:
            raise ProcessKilled("The process got killed (PID: %i)" % p.pid)
    
    @classmethod
    def try_receive(cls):
        """
        Retrieve a message from the current process' queue and return (True, message).
        If a message can't be retrieved now, return (False, None).
        """
        try:
            p = cls._current.p
        except NameError:
            raise Exception("The current thread has no PID")
        return p.queue.get_nowait()
    
    @classmethod
    def kill(cls, pid, flushQueue=True):
        """ Kill the specified process by closing its message queue. Return False on error. """
        pid = cls._to_pid(pid)
        with cls._lock:
            try:
                p = cls._processes[pid]
                queue = p.queue
            except KeyError:
                return False
        cls.logger().info("Killing process %i.", pid)
        queue.close(flushQueue)
        return True
    
    @classmethod
    def _to_pid(cls, pid):
        if hasattr(pid, "pid"):
            return pid.pid
        elif type(pid) is int:
            return pid
        else:
            raise Exception("Invalid PID '%s'" % repr(pid))
    
    @classmethod
    def _new_id(cls):
        id = cls._nextID
        cls._nextID += 1
        return id
    
    @classmethod
    def _create_process(cls, pid, name):
        p = cls(pid, name)
        cls._processes[pid] = p
        return p
    
    @classmethod
    def _set_current_process(cls, pid):
        cls._current.p = cls._processes[pid]
    
    @classmethod
    def _remove_current_process(cls, current_pid):
        p = cls._current.p
        p.queue.close()
        del cls._current.p
        #del cls._processes[current_pid]

class ProcessRunner(object):
    """ Run objects that have a run() method in a separate process. """
    def __init__(self, runnable, name=None):
        self.pid = None
        self.runnable = runnable
        if name:
            self.name = name
        else:
            self.name = runnable.__class__.__name__
    
    def __enter__(self):
        """ Start a new process to run the object. """
        self.start()
        return self
    
    def __exit__(self, type, val, tb):
        """ Stop the process if it is running. """
        self.stop()
    
    def start(self):
        """ Start a new process to run the object. """
        if not self.pid:
            p = self.runnable
            self.pid = Process.spawn(p.run, name=self.name)
        return self.pid
    
    def stop(self):
        """ Stop the process if it is running. """
        if self.pid:
            Process.try_send(self.pid, Command("stop"))
            self.pid = None

class ProcessExited(Exception):
    pass

class ProcessKilled(Exception):
    pass

class ProcessState(object):
    """ Object that can be used to store a process' state (which should not be shared across threads). """
    pass

class ProcessNotifier(object):
    """ Notifies other processes by sending messages. """
    def __init__(self, lock=None):
        self.__lock = lock or threading.Lock()
        self.__suscribers = set()
    
    def suscribe(self, pid=None):
        """ Suscribe a process to start receiving notifications. """
        if not pid:
            pid = Process.current()
            if not pid:
                raise Exception("The current thread has no PID")
        with self.__lock:
            self.__suscribers.add(pid)
    
    def unsuscribe(self, pid=None):
        """ Unsuscribe a process to stop receiving notifications. """
        if not pid:
            pid = Process.current()
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
                Process.send(pid, m)
            except Exception:
                pass

class ProcessMessage(Sequence):
    """ Base class for messages that can be sent to a process."""
    def __init__(self, name, *params):
        self.name = name
        self.params = params
    
    def __len__(self):
        return 1 + len(self.params)
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self)[index]
        if index == 0:
            return self.name
        elif (index > 0) and (index <= len(self.params)):
            return self.params[index - 1]
        else:
            raise IndexError("Index '%i' out of range" % index)
    
    def __str__(self):
        args = (self.name, ) + self.params
        return "%s(%s)" % (self.__class__.__name__, ", ".join(repr(a) for a in args))
    
    def __repr__(self):
        return self.__str__()

class Command(ProcessMessage):
    """ Contains information about a command sent to a process."""
    pass

class Event(ProcessMessage):
    """ Contains information about an event sent by a process. """
    pass

def match(pattern, o):
    """ Try to match an object against a pattern. Return True if the pattern is matched or False otherwise. """
    if (pattern is None) or (pattern == o):
        return True
    if type(pattern) is type:
        # match types
        return type(o) is pattern
    elif type(pattern) is str or type(pattern) is unicode:
        # match strings
        return pattern == o
    elif isinstance(pattern, Mapping):
        # match dicts
        if isinstance(o, Mapping):
            for key in pattern:
                if (not key in o) or (not match(pattern[key], o[key])):
                    return False
            return True
        else:
            return False
    elif isinstance(pattern, Sequence):
        # match lists
        if isinstance(o, Sequence):
            n = len(pattern)
            if n != len(o):
                return False
            else:
                for i in range(0, n):
                    if not match(pattern[i], o[i]):
                        return False
                return True
        else:
            return False
    else:
        # match attributes
        for name in dir(pattern):
            value = getattr(pattern, name)
            # ignore private and special attributes and functions
            if not name.startswith("_") and not hasattr(value, "__call__"):
                if not hasattr(o, name) or not match(value, getattr(o, name)):
                    return False
        return True

class EventSender(ProcessNotifier):
    """
    Event which can be suscribed by other processes.
    Example:
        EventSender("protocol-negociated", str) can send events such as
        Event("protocol-negociated", "SPARKv1") but not
        Event("protocol-negociated") or even
        Event("connected", "127.0.0.1:4550").
    """
    def __init__(self, name, *args):
        super(EventSender, self).__init__()
        self.pattern = Event(name, *args)
    
    def __call__(self, *args):
        """ Send a notification to all suscribed processes. """
        event = Event(self.pattern.name, *args)
        if match(self.pattern, event):
            super(EventSender, self).__call__(event)
        else:
            raise TypeError("%s doesn't match the pattern %s" %
                            (repr(event), repr(self.pattern)))

class MessageMatcher(object):
    """ Matches messages against a list of patterns. """
    def __init__(self):
        self.rules = []
    
    def addPattern(self, pattern, callable=None, result=True):
        """ Add a pattern to match messages. """
        self.rules.append((pattern, callable, result))
    
    def removePattern(self, pattern, callable=None, result=True):
        """ Remove a pattern from the list. """
        self.rules.remove((pattern, callable, result))
    
    def suscribeTo(self, sender, callable=None, result=True):
        """ Suscribe to an event after adding its pattern to the list. """
        self.addPattern(sender.pattern, callable, result)
        sender.suscribe()
    
    def match(self, m, *args):
        """ Match the message against the patterns. """
        for pattern, callable, result in reversed(self.rules):
            if match(pattern, m):
                if callable:
                    callable(m, *args)
                return result
        Process.logger().info("No rule matched message %s" % repr(m))
        return False
    
    def run(self, *args):
        """ Retrieve messages from the current process' queue while they match any pattern. """
        while True:
            m = Process.receive()
            if not self.match(m, *args):
                break