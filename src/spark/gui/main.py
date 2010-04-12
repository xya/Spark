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
from spark.fileshare import SharedFile, TransferInfo, UPLOAD, DOWNLOAD

__all__ = ["MainView"]

class MainView(object):
    def __init__(self, app):
        if not hasattr(MainView, "qtapp"):
            MainView.qtapp = QApplication(sys.argv)
        self.app = app
        self.window = MainWindow(app)
    
    def show(self):
        self.window.show()

class MainWindow(QMainWindow):
    def __init__(self, app, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowIcon(QIcon(iconPath("emblems/emblem-new", 16)))
        self.setWindowTitle("Spark")
        self.setMinimumSize(530, 360)
        self.app = app
        self.actions = {}
        self.initToolbar()
        self.initTransferList()
        self.initStatusBar()
        self.sharedFiles = {}
        self.fileIDs = []
        self.selectedID = None
        self.app.stateChanged += self.onStateChanged
        self.app.filesUpdated += self.onFilesUpdated
        self.updateStatusBar()
        self.updateToolBar()
    
    def createAction(self, icon, size, text, help=None):
        action = QAction(QIcon(iconPath(icon, size)), text, self)
        if help:
            action.setToolTip(help)
            action.setStatusTip(help)
        return action
    
    def initToolbar(self):
        self.actions["connect"] = self.createAction("status/network-transmit-receive", 32, "Connect", "Connect to a peer")
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
        for name in ("connect", "disconnect", None, "add", "remove", None,
                     "start", "pause", "stop", None, "open"):
            if name:
                self.toolbar.addAction(self.actions[name])
            else:
                self.toolbar.addSeparator()
        self.toolbar.setMovable(False)
        QObject.connect(self.actions["connect"], SIGNAL("triggered()"), self.action_connect)
        QObject.connect(self.actions["disconnect"], SIGNAL("triggered()"), self.action_disconnect)
        QObject.connect(self.actions["add"], SIGNAL("triggered()"), self.action_add)
        QObject.connect(self.actions["remove"], SIGNAL("triggered()"), self.action_remove)
        QObject.connect(self.actions["start"], SIGNAL("triggered()"), self.action_start)
    
    def updateToolBar(self):
        # connection-dependent actions
        self.actions["disconnect"].setVisible(self.app.isConnected)
        self.actions["connect"].setVisible(not self.app.isConnected)
        
        # selection-dependent actions
        if self.selectedID is None:
            file = None
        else:
            file = self.sharedFiles[self.selectedID]
        for key in ("add", "remove", "start", "pause", "stop", "open"):
            self.actions[key].setEnabled(self.isActionAvailable(key, file))
    
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
        if self.app.isConnected:
            self.connStatus.setPixmap(QPixmap(iconPath("status/network-idle", 24)))
            self.connStatus.setToolTip("Connected to a peer")
        else:
            self.connStatus.setPixmap(QPixmap(iconPath("status/network-offline", 24)))
            self.connStatus.setToolTip("Not connected")
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
        else:
            self.selectedID = self.fileIDs[index]
        self.updateToolBar()
    
    def isActionAvailable(self, name, file=None):
        """ Can the specified action be used now? """
        connected = self.app.isConnected
        if isinstance(file, basestring):
            file = self.sharedFiles[file]
        if name == "add":
            return True
        elif file is None:
            return False
        elif name == "remove":
            return file.ID in self.sharedFiles
        elif name == "start":
            return file.isRemote and connected
        elif name == "pause":
            return (file.isReceiving or file.isSending) and connected
        elif name == "stop":
            return (file.isReceiving or file.isSending) and connected
        elif name == "open":
            return file.isLocal
        else:
            return False
    
    def action_connect(self):
        d = ConnectionDialog(self.app, self)
        d.exec_()
    
    def action_disconnect(self):
        self.app.disconnect()
    
    def action_add(self):
        dir = os.path.expanduser("~")
        files = QFileDialog.getOpenFileNames(self, "Choose a file to open", dir, "All files (*.*)")
        if files.count() > 0:
            for file in files:
                self.app.addFile(str(file))
    
    def action_remove(self):
        if self.selectedID is not None:
            self.app.removeFile(self.selectedID)
    
    def action_start(self):
        if self.selectedID is not None:
            self.app.startTransfer(self.selectedID)
    
    def onFilesUpdated(self):
        self.updateTransferList(self.app.files)
    
    def onStateChanged(self):
        self.updateStatusBar()
        self.updateToolBar()

class ConnectionDialog(QDialog):
    def __init__(self, app, parent=None):
        super(ConnectionDialog, self).__init__(parent)
        self.app = app
        self.patterns = [
            (self.app.connected, self.connectOK),
            (self.app.connectionError, self.connectError)
        ]
        self.setWindowTitle("Connect to a peer")
        QObject.connect(self, SIGNAL('finished(int)'), self.closing)
        self.initWidgets()
        self.initLayout()
    
    def initWidgets(self):
        self.messageLabel = QLabel("Enter the peer's address and port below")
        self.hostText = QLineEdit("localhost")
        self.addressSeparator = QLabel(":")
        self.portText = QLineEdit("4550")
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(0)
        self.progressBar.setVisible(False)
        self.connectButton = QPushButton("Connect")
        self.cancelButton = QPushButton("Cancel")
        QObject.connect(self.connectButton, SIGNAL("clicked()"), self.doConnect)
        QObject.connect(self.cancelButton, SIGNAL("clicked()"), self, SLOT("reject()"))
    
    def initLayout(self):
        addressLayout = QBoxLayout(QBoxLayout.LeftToRight)
        addressLayout.addWidget(self.hostText, 4)
        addressLayout.addWidget(self.addressSeparator)
        addressLayout.addWidget(self.portText, 1)
        buttonLayout = QBoxLayout(QBoxLayout.LeftToRight)
        buttonLayout.addWidget(self.connectButton)
        buttonLayout.addWidget(self.cancelButton)
        mainLayout = QBoxLayout(QBoxLayout.TopToBottom, self)
        mainLayout.addWidget(self.messageLabel)
        mainLayout.addLayout(addressLayout)
        mainLayout.addWidget(self.progressBar)
        mainLayout.addLayout(buttonLayout)
    
    def closing(self):
        for delegate, callable in self.patterns:
            delegate -= callable
    
    def doConnect(self):
        address = (str(self.hostText.text()), int(self.portText.text()))
        self.connectButton.setEnabled(False)
        self.progressBar.setVisible(True)
        for delegate, callable in self.patterns:
            delegate += callable
        self.app.connect(address)
    
    def connectError(self, error):
        self.connectButton.setEnabled(True)
        self.progressBar.setVisible(False)
        QMessageBox.critical(self, "Connection error",
            "Error while connecting:\n%s" % str(error))
    
    def connectOK(self):
        self.connectButton.setEnabled(True)
        self.progressBar.setVisible(False)
        self.accept()