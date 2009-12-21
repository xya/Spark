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

import functools
import types
from spark.async import Reactor
from spark.messaging import TcpTransport, MessagingSession, Service
from spark.fileshare import FileShare

__all__ = ["SparkApplication", "Session"]

def sessionMethod(func):
    """ Invoke a callable in the context of the session. """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return self.reactor.send(func, *args, **kwargs)
    return wrapper

class SparkApplication(object):
    """ Hold the state of the whole application. """
    def __init__(self):
        self.reactor = Reactor.create()
        self.reactor.launch_thread()
        self.session = Session(self.reactor)
    
    @property
    def myIPaddress(self):
        """ Return the public IP address of the user, if known. """
        return "127.0.0.1"
    
    @property
    def activeTransfers(self):
        """ Return the number of active transfers. """
        return self.session.activeTransfers
    
    @property
    def uploadSpeed(self):
        """ Return the total upload speed, across all active transfers. """
        return self.session.uploadSpeed
    
    @property
    def downloadSpeed(self):
        """ Return the total download speed, across all active transfers. """
        return self.session.downloadSpeed
    
    Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
    def formatSize(self, size):
        for unit, count in reversed(SparkApplication.Units):
            if size >= count:
                return "%0.2f %s" % (size / float(count), unit)
        return "%d byte" % size

_fileShareMethods = ["files", "addFile", "removeFile"]

class Session(object):
    """
    Represent one session of file sharing. An user can share files with only
    one user per session.
    """
    def __init__(self, reactor):
        self.reactor = reactor
        self.transport = TcpTransport(reactor)
        self.messaging = MessagingSession(self.transport)
        self.share = FileShare(self.messaging)
        # wrap FileShare's methods so they are invoked on the reactor's thread
        for methodName in _fileShareMethods:
            method = sessionMethod(getattr(self.share, methodName))
            setattr(self, methodName, types.MethodType(method, self))
    
    @property
    def activeTransfers(self):
        """ Return the number of active transfers. """
        return 0
    
    @property
    def uploadSpeed(self):
        """ Return the total upload speed, across all active transfers. """
        return 0.0
    
    @property
    def downloadSpeed(self):
        """ Return the total download speed, across all active transfers. """
        return 0.0