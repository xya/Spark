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

def iconPath(name, size=None):
    if size:
        return "/usr/share/icons/gnome/%ix%i/%s.png" % (size, size, name)
    else:
        return "/usr/share/icons/gnome/scalable/%s.svg" % name

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
        self.actions["connect"] = self.createAction("status/network-transmit-receive", 32, "Connect", "Connect to a peer")
        #self.actions["disconnect"] = self.createAction("status/network-offline", 32, "Disconnect", "Close the connection to the peer")
        self.actions["add"] = self.createAction("actions/add", 32, "Add", "Add a file to the shared list")
        self.actions["remove"] = self.createAction("actions/process-stop", 32, "Remove", "Remove the file from the shared list")
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
        self.connStatus.setPixmap(QPixmap(iconPath("status/network-offline", 24)))
        self.connStatus.setToolTip("Not connected to a peer")
        self.myIP = QLabel("My IP: 127.0.0.1", self.statusBar())
        self.transferCount = QLabel("0 transfer(s)", self.statusBar())
        self.uploadSpeedIcon = QLabel(self.statusBar())
        self.uploadSpeedIcon.setPixmap(QPixmap(iconPath("actions/up", 24)))
        self.uploadSpeedText = QLabel("0 KiB/s", self.statusBar())
        self.downloadSpeedIcon = QLabel(self.statusBar())
        self.downloadSpeedIcon.setPixmap(QPixmap(iconPath("actions/down", 24)))
        self.downloadSpeedText = QLabel("0 KiB/s", self.statusBar())
        self.statusBar().addWidget(self.connStatus)
        self.statusBar().addWidget(self.myIP, 2)
        self.statusBar().addWidget(self.transferCount)
        self.statusBar().addWidget(self.uploadSpeedIcon)
        self.statusBar().addWidget(self.uploadSpeedText)
        self.statusBar().addWidget(self.downloadSpeedIcon)
        self.statusBar().addWidget(self.downloadSpeedText)
    
    def initFileList(self):
        sl = SharedFileList(self)
        sl.addFile("Report.pdf", "Size: 3 MiB", "mimetypes/gnome-mime-application-pdf",
                   None, None, "categories/applications-internet")
        sl.addFile("Spark-0.1_noarch.deb", "Size: 1 MiB", "mimetypes/deb",
                   "actions/go-home", None, "categories/applications-internet")
        sl.addFile("SeisRoX-2.0.9660.exe", "Received 5.25 MiB out of 22 MiB (24.5%)", "mimetypes/exec",
                   "actions/go-home", "actions/go-previous", "categories/applications-internet")
        sl.files[2].setTransferProgress(24)
        sl.files[2].setTransferTime("5 minutes left (50 KiB/s)")
        sl.addFile("TestArchive.zip", "Size: 117 MiB", "mimetypes/zip",
                   "actions/go-home", None, None)
        sl.addSpace()
        self.setCentralWidget(sl)

class SharedFileList(QWidget):
    def __init__(self, parent=None):
        super(SharedFileList, self).__init__(parent)
        self.files = []
        self.setLayout(QVBoxLayout())
    
    def addFile(self, name, size, icon, *args):
        widget = SharedFileWidget(self)
        widget.setName(name)
        widget.setTransferSize(size)
        widget.setTypeIcon(icon)
        for i, icon in enumerate(args):
            widget.setStatusIcon(icon, i)
        self.layout().addWidget(widget)
        self.files.append(widget)
    
    def addSpace(self):
        self.layout().addStretch()
        
class SharedFileWidget(QWidget):
    def __init__(self, parent=None):
        super(SharedFileWidget, self).__init__(parent)
        self.typeIcon = QLabel()
        self.typeIcon.setFixedSize(QSize(48, 48))
        self.statusIcons = [QLabel() for i in range(0, 3)]
        self.fileName = QLabel()
        self.transferSize = QLabel()
        self.transferTime = QLabel()
        self.transferProgress = QProgressBar()
        self.transferProgress.setTextVisible(False)
        self.transferProgress.setMaximumHeight(16)
        self.transferProgress.hide()
        self.statusTooltip = ["Local file", "Transfering", "Remote file"]
        
        status = QHBoxLayout()
        for statusIcon in self.statusIcons:
            statusIcon.setFixedSize(QSize(16, 16))
            status.addWidget(statusIcon)
        transferInfo = QHBoxLayout()
        transferInfo.setSpacing(20)
        transferInfo.addWidget(self.transferSize)
        transferInfo.addStretch()
        transferInfo.addWidget(self.transferTime)
        content = QVBoxLayout()
        content.setSpacing(0)
        content.addWidget(self.fileName)
        content.addLayout(transferInfo)
        grid = QGridLayout()
        grid.addWidget(self.typeIcon, 0, 0, Qt.AlignCenter)
        grid.addLayout(content, 0, 1, Qt.AlignVCenter)
        grid.addLayout(status, 1, 0)
        grid.addWidget(self.transferProgress, 1, 1)
        self.setLayout(grid)
    
    def setName(self, name):
        self.fileName.setText(name)
    
    def setTransferSize(self, size):
        self.transferSize.setText(size)
    
    def setTransferTime(self, time):
        self.transferTime.setText(time)
    
    def setTypeIcon(self, icon):
        self.typeIconSet = QIcon(iconPath(icon))
        self.typeIcon.setPixmap(self.typeIconSet.pixmap(48, 48))
    
    def setStatusIcon(self, icon, index):
        statusIcon = self.statusIcons[index]
        if icon:
            statusIcon.setPixmap(QPixmap(iconPath(icon, 16)))
            statusIcon.setToolTip(self.statusTooltip[index])
        else:
            statusIcon.setPixmap(QPixmap())
            statusIcon.setToolTip("")
    
    def setStatusToolTip(self, text, index):
        statusIcon = self.statusIcons[index]
        statusIcon.setToolTip(text)
    
    def setTransferProgress(self, progress):
        if progress:
            self.transferProgress.setValue(progress)
            self.transferProgress.show()
        else:
            self.transferProgress.hide()