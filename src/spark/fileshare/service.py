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
import threading
from spark.async import Future
from spark.messaging import MessengerService
from spark.messaging import MessageDelivery

__all__ = ["FileShare"]

class FileShare(MessengerService, MessageDelivery):
    """ Service that shares files over a network. """
    def __init__(self):
        super(FileShare, self).__init__()
        self.onMessageReceived = self.deliverMessage
    
    def onDisconnected(self):
        try:
            self.resetDelivery()
        finally:
            super(FileShare, self).onDisconnected()
    
    def requestReceived(self, m):
        pass
    
    def notificationReceived(self, m):
        pass
    
    def blockReceived(self, m):
        pass