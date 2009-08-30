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

from spark.async import Future, asyncMethod
from spark.session import Session
from spark.messaging import MessageDelivery
from local import LocalFileShare
from remote import RemoteFileShare

__all__ = ["FileShareSession"]

class FileShareSession(Session, MessageDelivery):
    def __init__(self):
        super(FileShareSession, self).__init__()
        self.localShare = None
        self.remoteShare = None
    
    def handleMessage(self, message):
        #print("Received '%s'" % str(message))
        self.deliverMessage(message)
    
    def sessionStarted(self):
        self.localShare = LocalFileShare(self)
        self.remoteShare = RemoteFileShare(self)
    
    def sessionCleanup(self):
        try:
            if self.remoteShare:
                self.remoteShare.close()
            if self.localShare:
                self.localShare.close()
            self.resetDelivery()
        finally:
            super(FileShareSession, self).sessionCleanup()