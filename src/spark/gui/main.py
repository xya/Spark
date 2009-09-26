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
from spark.fileshare.files import SharedList, SharedFile
from spark.fileshare.common import TransferInfo, TransferLocation

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
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(iconPath("emblems/emblem-new", 16)))
        self.setWindowTitle("Spark")
        self.actions = {}
        self.initToolbar()
        self.initTransferList()
        self.initStatusBar()
        self.sharedFiles = SharedList()
        self.sharedFiles.updated += self.sharedFilesUpdated
        self.createSharedFiles()
    
    def createSharedFiles(self):
        self.sharedFiles.addFile(SharedFile("Report.pdf", 3 * 1024 * 1024,
            mimeType="mimetypes/gnome-mime-application-pdf"))
        self.sharedFiles.addFile(SharedFile("Spark-0.1_noarch.deb", 1 * 1024 * 1024,
            mimeType="mimetypes/deb"))
        self.sharedFiles.addFile(SharedFile("SeisRoX-2.0.9660.exe", 1 * 1024 * 1024,
            mimeType="mimetypes/deb"))
        self.sharedFiles.addFile(SharedFile("TestArchive.zip", 117 * 1024 * 1024,
            mimeType="mimetypes/zip"))
    
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
    
    def initStatusBar(self):
        self.connStatus = QLabel(self.statusBar())
        self.myIP = QLabel(self.statusBar())
        self.transferCount = QLabel(self.statusBar())
        self.uploadSpeedIcon = QLabel(self.statusBar())
        self.uploadSpeedIcon.setPixmap(QPixmap(iconPath("actions/up", 24)))
        self.uploadSpeedText = QLabel(self.statusBar())
        self.downloadSpeedIcon = QLabel(self.statusBar())
        self.downloadSpeedIcon.setPixmap(QPixmap(iconPath("actions/down", 24)))
        self.downloadSpeedText = QLabel(self.statusBar())
        self.statusBar().addWidget(self.connStatus)
        self.statusBar().addWidget(self.myIP, 2)
        self.statusBar().addWidget(self.transferCount)
        self.statusBar().addWidget(self.uploadSpeedIcon)
        self.statusBar().addWidget(self.uploadSpeedText)
        self.statusBar().addWidget(self.downloadSpeedIcon)
        self.statusBar().addWidget(self.downloadSpeedText)
    
    def updateStatusBar(self):
        self.connStatus.setPixmap(QPixmap(iconPath("status/network-idle", 24)))
        self.connStatus.setToolTip("Connected to a peer")
        self.myIP.setText("My IP: 127.0.0.1")
        self.transferCount.setText("%d transfer(s)" % self.sharedFiles.activeTransfers)
        self.uploadSpeedText.setText("%s/s" % self.formatSize(self.sharedFiles.uploadSpeed))
        self.downloadSpeedText.setText("%s/s" % self.formatSize(self.sharedFiles.downloadSpeed))
    
    def initTransferList(self):
        self.transferList = FileList()
        self.connect(self.transferList, SIGNAL("selectionChanged"), self.updateSelectedTransfer)
        self.setCentralWidget(self.transferList)
        self.transferList.setFocus()
    
    def updateTransferList(self):
        self.transferList.clear()
        for file in self.sharedFiles:
            self.transferList.addItem(self.createFileWidget(file))
        self.transferList.addSpace()
        self.updateSelectedTransfer(-1)
    
    def createFileWidget(self, file):
        widget = FileInfoWidget(self)
        widget.setName(file.name)
        widget.setTransferSize("Size: %s" % self.formatSize(file.size))
        if file.mimeType:
            widget.setTypeIcon(file.mimeType)
        widget.setStatusIcon(file.isLocal and "actions/go-home" or None, 0)
        if file.isReceiving:
            widget.setStatusIcon("actions/go-previous", 1)
        elif file.isSending:
            widget.setStatusIcon("actions/go-next", 1)
        else:
            widget.setStatusIcon(None, 1)
        widget.setStatusIcon(file.isRemote and "categories/applications-internet" or None, 2)
        if file.transfer:
            widget.setTransferProgress(file.transfer.progress)
            widget.setTransferTime(file.transfer.duration)
        return widget
    
    def updateSelectedTransfer(self, index):
        file = self.sharedFiles[index]
        for key in ("add", "remove", "start", "pause", "stop", "open"):
            self.actions[key].setEnabled(self.sharedFiles.isActionAvailable(key, file))
    
    def sharedFilesUpdated(self):
        self.updateTransferList()
        self.updateStatusBar()
    
    Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
    def formatSize(self, size):
        for unit, count in reversed(MainWindow.Units):
            if size >= count:
                return "%0.2f %s" % (size / float(count), unit)
        return "%d byte" % size