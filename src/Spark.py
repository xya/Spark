#!/usr/bin/env python
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

import sys
import os
import logging
from PyQt4.QtCore import QObject, QEvent
from PyQt4.QtGui import QApplication
from spark.gui.main import MainWindow
from spark.fileshare import SparkApplication
from spark.async import Process, PatternMatcher

class GuiProcess(QObject):
    def __init__(self):
        super(GuiProcess, self).__init__()
        self.pid = Process.attach("GUI", self)
        self.messages = PatternMatcher()
    
    def __enter__(self):
        return self
    
    def __exit__(self, type, e, traceback):
        Process.detach()
    
    def event(self, ev):
        """ Handle events sent to the object. """
        if ev.type() == MessageReceivedEvent.Type:
            self.messages.match(ev.m)
            return True
        else:
            return False
    
    def put(self, m):
        """ Add a process message to the message loop's queue. """
        QApplication.postEvent(self, MessageReceivedEvent(m))
    
    def get(self):
        raise Exception("Can't receive messages on the GUI thread. " +
                        "Use the message matching mechanism instead.")
    
    def try_get(self):
        return (False, None)
    
    def close(self):
        pass

class MessageReceivedEvent(QEvent):
    """ A message was received by a process. """
    Type = QEvent.registerEventType()
    def __init__(self, m):
        super(MessageReceivedEvent, self).__init__(MessageReceivedEvent.Type)
        self.m = m

if __name__ == "__main__":
    if (len(sys.argv) > 1) and (sys.argv[1].find(":") >= 0):
        chunks = sys.argv[1].split(":")
        bindAddr = (chunks[0], int(chunks[1]))
    else:
        bindAddr = None
    qtapp = QApplication(sys.argv)
    logging.basicConfig(level=logging.DEBUG)
    with GuiProcess() as pid:
        with SparkApplication() as app:
            app.installHandlers(pid.messages)
            view = MainWindow(app)
            if bindAddr:
                view.setWindowTitle("Spark %s:%i" % bindAddr)
                app.bind(bindAddr)
            else:
                view.setWindowTitle("Spark")
            view.show()
            qtapp.exec_()