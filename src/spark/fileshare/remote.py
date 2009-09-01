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

from types import MethodType
from spark.messaging import Request
from spark.fileshare.common import FileShare, toCamelCase

__all__ = ["RemoteFileShare"]

class RemoteFileShare(FileShare):
    def __init__(self, delivery):
        super(RemoteFileShare, self).__init__()
        self.delivery = delivery
        delivery.notificationReceived += self.notificationReceived
        for tag in FileShare.Notifications:
            self.createEvent(tag)
        for tag in FileShare.Requests:
            self.createRequest(tag, self.requestHandler(tag))
    
    def requestHandler(self, tag):
        """ Create a function to handle sending requests with the given tag """
        def handler(self, params):
            return self.delivery.sendRequest(Request(tag, params))
        return MethodType(handler, self)
    
    def notificationReceived(self, n):
        self.invokeEvent(n.tag, n.params)