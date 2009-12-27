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

""" Manage the execution flow of tasks. """
import os
import socket
import threading
from spark.async import Reactor, BlockingQueue

try:
    import stackless
    _reactor = Reactor.create()
except ImportError:
    _threads = []
    
    def new_task(callable, *args, **kw):
        """ Create a new task. """
        global _threads
        t = threading.Thread(target=callable, args=args, kwargs=kw)
        t.daemon = True
        _threads.append(t)
    
    def open_file(path, mode=None):
        """ Create or open a file. """
        return open(path, mode)
        
    def new_pipe():
        """ Create a pipe. """
        readFD, writeFD = os.pipe()
        return os.fdopen(readFD, 'r', 0), os.fdopen(writeFD, 'w', 0)
        
    def new_socket(family, type, protocol):
        """ Create a socket. """
        return socket.socket(family, type, protocol)
    
    def new_queue():
        """ Create a (blocking) queue that can be used to communicate between tasks. """
        return BlockingQueue(32)
    
    def run():
        """ Execute all tasks until they return (?) """
        global _threads
        for thread in _threads:
            thread.start()
        for thread in _threads:
            thread.join()
        _threads = []
else:
    _running = 0
    
    def new_task(callable, *args, **kw):
        """ Create a new task. """
        # HACK, fix Reactor to handle tasks
        def _run_task():
            global _running
            _running += 1
            callable(*args, **kw)
            _running -= 1
            if _running == 0:
                _reactor.close()
        stackless.tasklet(_run_task)()
    
    def open_file(path, mode=None):
        """ Create or open a file. """
        return _reactor.open(path, mode)
        
    def new_pipe():
        """ Create a pipe. """
        return _reactor.pipe()
        
    def new_socket(family, type, protocol):
        """ Create a socket. """
        return _reactor.socket(family, type, protocol)
    
    def new_queue():
        """ Create a (blocking) queue that can be used to communicate between tasks. """
        return stackless.channel()
    
    def run():
        """ Execute all tasks until they return (?) """
        _reactor.run()