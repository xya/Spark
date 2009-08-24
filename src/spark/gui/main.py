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
from spark.gui.filelist import FileList, FileInfoWidget, iconPath

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
        self.setWindowIcon(QIcon(iconPath("emblems/emblem-new", 16)))
        self.setWindowTitle("Spark")
        self.actions = {}
        self.initToolbar()
        self.initFileList()
        self.initStatusBar()
    
    def createAction(self, icon, size, text, help=None):
        action = QAction(QIcon(iconPath(icon, size)), text, self)
        if help:
            action.setToolTip(help)
            action.setStatusTip(help)
        return action
    
    def initToolbar(self):
        #self.actions["connect"] = self.createAction("status/network-transmit-receive", 32, "Connect", "Connect to a peer")
        self.actions["disconnect"] = self.createAction("actions/process-stop", 32, "Disconnect", "Close the connection to the peer")
        self.actions["add"] = self.createAction("actions/list-add", 32, "Add", "Add a file to the list")
        self.actions["remove"] = self.createAction("actions/list-remove", 32, "Remove", "Remove the file from the list")
        self.actions["start"] = self.createAction("actions/media-playback-start", 32, "Start", "Start receiving the file")
        self.actions["pause"] = self.createAction("actions/media-playback-pause", 32, "Pause", "Pause the transfer")
        self.actions["stop"] = self.createAction("actions/media-playback-stop", 32, "Stop", "Cancel the transfer")
        self.actions["open"] = self.createAction("places/folder-saved-search", 32, "Open", "Open the file")
        
        self.toolbar = self.addToolBar("Actions")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for name in ("disconnect", None, "add", "remove", None, "start", "pause", "stop", None, "open"):
            if name:
                self.toolbar.addAction(self.actions[name])
            else:
                self.toolbar.addSeparator()
        self.toolbar.setMovable(False)
        self.updateSelectedFile(-1)
    
    def initStatusBar(self):
        self.connStatus = QLabel(self.statusBar())
        self.connStatus.setPixmap(QPixmap(iconPath("status/network-idle", 24)))
        self.connStatus.setToolTip("Connected to a peer")
        self.myIP = QLabel("My IP: 127.0.0.1", self.statusBar())
        self.transferCount = QLabel("1 transfer(s)", self.statusBar())
        self.uploadSpeedIcon = QLabel(self.statusBar())
        self.uploadSpeedIcon.setPixmap(QPixmap(iconPath("actions/up", 24)))
        self.uploadSpeedText = QLabel("0 KiB/s", self.statusBar())
        self.downloadSpeedIcon = QLabel(self.statusBar())
        self.downloadSpeedIcon.setPixmap(QPixmap(iconPath("actions/down", 24)))
        self.downloadSpeedText = QLabel("50 KiB/s", self.statusBar())
        self.statusBar().addWidget(self.connStatus)
        self.statusBar().addWidget(self.myIP, 2)
        self.statusBar().addWidget(self.transferCount)
        self.statusBar().addWidget(self.uploadSpeedIcon)
        self.statusBar().addWidget(self.uploadSpeedText)
        self.statusBar().addWidget(self.downloadSpeedIcon)
        self.statusBar().addWidget(self.downloadSpeedText)
    
    def initFileList(self):
        self.sharedFiles = FileList()
        file = self.createFile("Report.pdf", "Size: 3 MiB", "mimetypes/gnome-mime-application-pdf",
                   None, None, "categories/applications-internet")
        self.sharedFiles.addItem(file)
        
        file = self.createFile("Spark-0.1_noarch.deb", "Size: 1 MiB", "mimetypes/deb",
                   "actions/go-home", None, "categories/applications-internet")
        file.setTransferTime("Received in 10 secondes (100 KiB/s)")
        self.sharedFiles.addItem(file)
        
        file = self.createFile("SeisRoX-2.0.9660.exe", "Received 5.25 MiB out of 22 MiB (24.5%)", "mimetypes/exec",
                   "actions/go-home", "actions/go-previous", "categories/applications-internet")
        file.setTransferProgress(24)
        file.setTransferTime("5 minutes left (50 KiB/s)")
        self.sharedFiles.addItem(file)
        
        file = self.createFile("TestArchive.zip", "Size: 117 MiB", "mimetypes/zip",
                   "actions/go-home", None, None)
        self.sharedFiles.addItem(file)
        
        self.sharedFiles.addSpace()
        self.connect(self.sharedFiles, SIGNAL("selectionChanged"), self.updateSelectedFile)
        
        self.setCentralWidget(self.sharedFiles)
        self.sharedFiles.setFocus()
    
    def createFile(self, name, size, icon, *args):
        widget = FileInfoWidget(self)
        widget.setName(name)
        widget.setTransferSize(size)
        widget.setTypeIcon(icon)
        for i, icon in enumerate(args):
            widget.setStatusIcon(icon, i)
        return widget
    
    def updateSelectedFile(self, index):
        keys = ["remove", "start", "pause", "stop", "open"]
        if index < 0:
            values = [False, False, False, False, False]
        elif index == 0:
            values = [True, True, False, False, False]
        elif (index == 1) or (index == 3):
            values = [True, False, False, False, True]
        elif index == 2:
            values = [False, False, True, True, False]
        for key, value in zip(keys, values):
            self.actions[key].setEnabled(value)
