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

__all__ = ["Reactor"]

class Reactor(object):
    """
    Manages asynchronous I/O and non-IO operations.
    
    All callbacks (callable passed to the invoke function and I/O Future callbacks)
    are guaranteed to be executed on the same thread ("reactor thread").
    """
    
    def launch_thread(self):
        """ Start a background thread to run the reactor. """
        raise NotImplementedError()
    
    def run(self):
        """ Run the reactor on the current thread. """
        raise NotImplementedError()
    
    def close(self):
        """ Close the reactor, terminating all pending operations. """
        raise NotImplementedError()
    
    def read(self, file, size):
        """ Submit a request to perform a read operation on the file. """
        raise NotImplementedError()
    
    def write(self, file, data):
        """ Submit a request to perform a write operation on the file. """
        raise NotImplementedError()
    
    def connect(self, socket, address):
        """ Submit a request to perform a connect operation on the socket. """
        raise NotImplementedError()
    
    def accept(self, socket):
        """ Submit a request to perform an accept operation on the socket. """
        raise NotImplementedError()
    
    def socket(self, family=None, type=None, proto=None):
        """ Create a socket that uses the reactor to do asynchronous I/O. """
        raise NotImplementedError()
    
    def invoke(self, fun, *args):
        """ Submit a request to invoke a callable. """
        raise NotImplementedError()