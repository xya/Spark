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
from PyQt4.QtCore import *
from PyQt4.QtGui import *

__all__ = ["MainView"]

class MainView(object):
    def __init__(self):
        if not hasattr(MainView, "app"):
            MainView.app = QApplication(sys.argv)
        self.window = MainWindow()
    
    def show(self):
        self.window.show()
        MainView.app.exec_()

class MainWindow(QMainWindow):
    #toolbarActions = [
    #    ("status/network-transmit-receive", "Connect"),
    #    
    #]
    
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(self.iconPath("emblems/emblem-new", 16)))
        self.setWindowTitle("Spark")
        self.resize(800, 600)
        self.actions = {}
        self.initToolbar()
        self.initStatusBar()
    
    def iconPath(self, name, size):
        return "/usr/share/icons/gnome/%ix%i/%s.png" % (size, size, name)
    
    def createAction(self, icon, size, text, help=None):
        action = QAction(QIcon(self.iconPath(icon, size)), text, self)
        if help:
            action.setToolTip(help)
            action.setStatusTip(help)
        return action
    
    def initToolbar(self):
        self.actions["connect"] = self.createAction("status/network-transmit-receive", 32, "Connect", "Connect to a peer")
        #self.actions["disconnect"] = self.createAction("status/network-offline", 32, "Disconnect", "Close the connection to the peer")
        self.actions["add"] = self.createAction("actions/add", 32, "Add", "Add a file to the shared list")
        self.actions["remove"] = self.createAction("actions/remove", 32, "Remove", "Remove a file from the shared list")
        self.actions["start"] = self.createAction("actions/media-playback-start", 32, "Start", "Start receiving the file")
        self.actions["pause"] = self.createAction("actions/media-playback-pause", 32, "Pause", "Pause the transfer")
        self.actions["stop"] = self.createAction("actions/media-playback-stop", 32, "Stop", "Cancel the transfer")
        self.actions["open"] = self.createAction("places/folder-saved-search", 32, "Open", "Open the file")
        
        self.toolbar = self.addToolBar("Actions")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for name in ("connect", None, "add", "remove", None, "start", "pause", "stop", None, "open"):
            if name:
                self.toolbar.addAction(self.actions[name])
            else:
                self.toolbar.addSeparator()
        self.toolbar.setMovable(False)
    
    def initStatusBar(self):
        self.connStatus = QLabel(self.statusBar())
        self.connStatus.setPixmap(QPixmap(self.iconPath("status/network-offline", 24)))
        self.connStatus.setToolTip("Not connected to a peer")
        self.myIP = QLabel("My IP: 127.0.0.1", self.statusBar())
        self.transferCount = QLabel("0 transfer(s)", self.statusBar())
        self.uploadSpeedIcon = QLabel(self.statusBar())
        self.uploadSpeedIcon.setPixmap(QPixmap(self.iconPath("actions/up", 24)))
        self.uploadSpeedText = QLabel("0 KiB/s", self.statusBar())
        self.downloadSpeedIcon = QLabel(self.statusBar())
        self.downloadSpeedIcon.setPixmap(QPixmap(self.iconPath("actions/down", 24)))
        self.downloadSpeedText = QLabel("0 KiB/s", self.statusBar())
        self.statusBar().addWidget(self.connStatus)
        self.statusBar().addWidget(self.myIP, 2)
        self.statusBar().addWidget(self.transferCount)
        self.statusBar().addWidget(self.uploadSpeedIcon)
        self.statusBar().addWidget(self.uploadSpeedText)
        self.statusBar().addWidget(self.downloadSpeedIcon)
        self.statusBar().addWidget(self.downloadSpeedText)
        