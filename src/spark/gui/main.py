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
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from spark.gui.filelist import FileList, FileInfoWidget, iconPath
from spark.fileshare import SharedFile, TransferInfo, TransferLocation

__all__ = ["MainView"]

class MainView(object):
    def __init__(self, app):
        if not hasattr(MainView, "qtapp"):
            MainView.qtapp = QApplication(sys.argv)
        self.app = app
        self.window = MainWindow(app)
    
    def show(self):
        self.window.show()
        MainView.qtapp.exec_()

class MainWindow(QMainWindow):
    def __init__(self, app, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(iconPath("emblems/emblem-new", 16)))
        self.setWindowTitle("Spark")
        self.setMinimumSize(429, 360)
        self.app = app
        self.actions = {}
        self.initToolbar()
        self.initTransferList()
        self.initStatusBar()
        self.sharedFiles = {}
        self.fileIDs = []
        self.selectedID = None
        self.app.session.share.filesUpdated += onGuiThread(self.sharedFilesUpdated)
        self.sharedFilesUpdated()
    
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
        QObject.connect(self.actions["add"], SIGNAL("triggered()"), self.action_add)
        QObject.connect(self.actions["remove"], SIGNAL("triggered()"), self.action_remove)
    
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
        self.myIP.setText("My IP: %s" % self.app.myIPaddress)
        self.transferCount.setText("%d transfer(s)" % self.app.activeTransfers)
        self.uploadSpeedText.setText("%s/s" % self.app.formatSize(self.app.uploadSpeed))
        self.downloadSpeedText.setText("%s/s" % self.app.formatSize(self.app.downloadSpeed))
    
    def initTransferList(self):
        self.transferList = FileList()
        self.connect(self.transferList, SIGNAL("selectionChanged"), self.updateSelectedTransfer)
        self.setCentralWidget(self.transferList)
        self.transferList.setFocus()
    
    def updateTransferList(self, files):
        self.transferList.clear()
        self.sharedFiles = files
        self.fileIDs = files.keys()
        for file in (self.sharedFiles[ID] for ID in self.fileIDs):
            self.transferList.addItem(self.createFileWidget(file))
        self.transferList.addSpace()
        self.updateSelectedTransfer(-1)
    
    def createFileWidget(self, file):
        widget = FileInfoWidget(self)
        widget.setName(file.name)
        widget.setTransferSize("Size: %s" % self.app.formatSize(file.size))
        if file.mimeType:
            widget.setTypeIcon("mimetypes/%s" % file.mimeType)
        else:
            widget.setTypeIcon("mimetypes/gtk-file")
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
        if index < 0:
            self.selectedID = None
            file = None
        else:
            self.selectedID = self.fileIDs[index]
            file = self.sharedFiles[self.selectedID]
        for key in ("add", "remove", "start", "pause", "stop", "open"):
            self.actions[key].setEnabled(self.isActionAvailable(key, file))
    
    def isActionAvailable(self, name, file=None):
        """ Can the specified action be used now? """
        if isinstance(file, basestring):
            file = self.sharedFiles[file]
        if name == "add":
            return True
        elif file is None:
            return False
        elif name == "remove":
            return file.ID in self.sharedFiles
        elif name == "start":
            return file.isRemote
        elif name == "pause":
            return file.isReceiving or file.isSending
        elif name == "stop":
            return file.isReceiving or file.isSending
        elif name == "open":
            return file.isLocal
        else:
            return False
    
    def action_add(self):
        dir = os.path.expanduser("~")
        files = QFileDialog.getOpenFileNames(self, "Choose a file to open", dir, "All files (*.*)")
        if files.count() > 0:
            for file in files:
                self.app.session.addFile(str(file)).after(onGuiThread(self.end_addFile))
    
    def end_addFile(self, prev):
        result = prev.result
    
    def action_remove(self):
        if self.selectedID is not None:
            self.app.session.removeFile(self.selectedID).after(
                onGuiThread(self.end_removeFile))
    
    def end_removeFile(self, prev):
        result = prev.result
    
    def sharedFilesUpdated(self):
        self.updateStatusBar()
        self.app.session.files().after(lambda prev: self.updateTransferList(prev.result))

class Invoker(QObject):
    def __init__(self):
        super(Invoker, self).__init__()
    
    def event(self, ev):
        """ Handle events sent to the object. """
        if ev.type() == InvokeEvent.Type:
            ev()
            return True
        else:
            return False

class InvokeEvent(QEvent):
    """ Hold information about a function to invoke. """
    Type = QEvent.registerEventType()
    def __init__(self, func, *args, **kwargs):
        super(InvokeEvent, self).__init__(InvokeEvent.Type)
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self):
        """ Invoke the function. """
        self.func(*self.args, **self.kwargs)

_invoker = Invoker()

def onGuiThread(func):
    """  Invoke the function on the application's GUI thread. """
    def wrapper(*args, **kwargs):
        QApplication.postEvent(_invoker, InvokeEvent(func, *args, **kwargs))
    return wrapper