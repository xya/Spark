# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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
import functools
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from spark.gui.resource import iconPath
from spark.gui.filelist import FileList, FileInfoWidget
from spark.gui.about import AboutWindow
from spark.gui import filetypes
from spark.fileshare import UPLOAD, DOWNLOAD, LOCAL, REMOTE
from spark.fileshare import SharedFile, TransferInfo, formatSize, formatDuration

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
        self.setWindowIcon(QIcon(iconPath("apps/spark", 16)))
        self.setWindowTitle("Spark")
        self.setMinimumSize(530, 360)
        self.aboutWindow = AboutWindow(self)
        self.app = app
        self.actions = {}
        self.initMenu()
        self.initToolbar()
        self.initTransferList()
        self.initStatusBar()
        self.initTrayIcon()
        self.initTimer()
        self.sharedFiles = {}
        self.fileIDs = []
        self.selectedID = None
        self.lastUsedFolder = os.path.expanduser("~")
        self.app.listening += self.onStateChanged
        self.app.connected += self.onStateChanged
        self.app.disconnected += self.onStateChanged
        self.app.stateChanged += self.onStateChanged
        self.app.fileListUpdated += self.onStateChanged
        self.app.fileUpdated += self.onFileUpdated
        self.updateStatusBar()
        self.updateToolBar()
    
    def createAction(self, icon, size, text, help=None):
        path = iconPath(icon, size)
        if path:
            action = QAction(QIcon(path), text, self)
        else:
            action = QAction(text, self)
        if help:
            action.setToolTip(help)
            action.setStatusTip(help)
        return action
    
    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                self.hide()
                self.trayIcon.setVisible(True)
    
    def initMenu(self):
        self.actions["quit"] = self.createAction("actions/application-exit", 16, "Quit", "Quit the application")
        self.actions["about"] = self.createAction("actions/help-about", 16, "About", "About Spark")
        QWidget.connect(self.actions["quit"], SIGNAL("triggered()"), self, SLOT("close()"))
        QWidget.connect(self.actions["about"], SIGNAL("triggered()"), self.aboutWindow, SLOT("show()"))
        self.fileMenu = QMenu()
        self.fileMenu.setTitle("File")
        self.fileMenu.addAction(self.actions["quit"])
        self.helpMenu = QMenu()
        self.helpMenu.setTitle("Help")
        self.helpMenu.addAction(self.actions["about"])
        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.helpMenu)
    
    def initToolbar(self):
        self.actions["connect"] = self.createAction("status/network-transmit-receive", 32, "Connect", "Connect to a peer")
        self.actions["disconnect"] = self.createAction("actions/process-stop", 32, "Disconnect", "Close the connection to the peer")
        self.actions["add"] = self.createAction("actions/list-add", 32, "Add", "Add a file to the list")
        self.actions["remove"] = self.createAction("actions/list-remove", 32, "Remove", "Remove the file from the list")
        self.actions["start"] = self.createAction("actions/media-playback-start", 32, "Receive", "Start receiving the file")
        self.actions["pause"] = self.createAction("actions/media-playback-pause", 32, "Pause", "Pause the transfer")
        self.actions["stop"] = self.createAction("actions/media-playback-stop", 32, "Stop", "Cancel the transfer")
        self.actions["open"] = self.createAction("places/folder-saved-search", 32, "Open", "Open the file")
        
        self.toolbar = self.addToolBar("Actions")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        for name in ("connect", "disconnect", None, "add", "remove",
                     "start", "pause", "stop", "open"):
            if name:
                self.toolbar.addAction(self.actions[name])
            else:
                self.toolbar.addSeparator()
        self.toolbar.setMovable(False)
        for name in ("connect", "disconnect", "add", "remove", "start", "open"):
            handler = functools.partial(self.performAction, name)
            QObject.connect(self.actions[name], SIGNAL("triggered()"), handler)
    
    def updateToolBar(self):
        # connection-dependent actions
        self.actions["disconnect"].setVisible(self.app.isConnected)
        self.actions["connect"].setVisible(not self.app.isConnected)
        
        # selection-dependent actions
        if not self.selectedID in self.sharedFiles:
            file = None
        else:
            file = self.sharedFiles[self.selectedID]
        for key in ("add", "remove", "start", "pause", "stop", "open"):
            available = self.isActionAvailable(key, file)
            self.actions[key].setEnabled(available)
            self.actions[key].setVisible(available)
    
    def initStatusBar(self):
        self.connStatus = QLabel(self.statusBar())
        self.myIP = QLabel(self.statusBar())
        self.transferCount = QLabel(self.statusBar())
        self.uploadSpeedIcon = QLabel(self.statusBar())
        self.uploadSpeedIcon.setPixmap(QPixmap(iconPath("actions/go-up", 24)))
        self.uploadSpeedText = QLabel(self.statusBar())
        self.downloadSpeedIcon = QLabel(self.statusBar())
        self.downloadSpeedIcon.setPixmap(QPixmap(iconPath("actions/go-down", 24)))
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
            connStatus = "Connected to %s:%d" % self.app.connectionAddress
            self.connStatus.setPixmap(QPixmap(iconPath("status/network-idle", 24)))
        else:
            connStatus = "Not connected to a peer"
            self.connStatus.setPixmap(QPixmap(iconPath("status/network-offline", 24)))
        if self.app.isListening:
            listenStatus = "Listening for incoming connections on %s:%d" % self.app.bindAddress
            self.setWindowTitle("Spark - %s:%d" % self.app.bindAddress)
        else:
            self.setWindowTitle("Spark")
            listenStatus = "Not listening for incoming connections"
        self.trayIcon.setToolTip(self.windowTitle())
        self.connStatus.setToolTip(connStatus + "\n" + listenStatus)
        self.myIP.setText("My IP: %s" % self.app.myIPaddress)
        self.transferCount.setText("%d transfer(s)" % self.app.activeTransfers)
        self.uploadSpeedText.setText(formatSize(self.app.uploadSpeed, "%s/s"))
        self.downloadSpeedText.setText(formatSize(self.app.downloadSpeed, "%s/s"))
    
    def initTrayIcon(self):
        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(QIcon(QPixmap(iconPath("apps/spark", 24))))
        self.trayIcon.setToolTip(self.windowTitle())
        self.trayMenu = QMenu(self)
        quit = QAction("Quit", self)
        self.trayMenu.addAction(quit)
        self.trayIcon.setContextMenu(self.trayMenu)
        QObject.connect(self.trayIcon,
            SIGNAL("activated(QSystemTrayIcon::ActivationReason)"), self.trayIconActivated)
        QObject.connect(quit, SIGNAL("triggered()"), self, SLOT("close()"))
    
    def trayIconActivated(self, reason):
        if (reason == QSystemTrayIcon.DoubleClick) or (reason == QSystemTrayIcon.Trigger):
            if not self.isVisible():
                self.showNormal()
                self.trayIcon.setVisible(False)
    
    def initTransferList(self):
        self.transferList = FileList()
        self.connect(self.transferList, SIGNAL("selectionChanged"), self.updateSelectedTransfer)
        self.connect(self.transferList, SIGNAL("itemActivated"), self.performDefaultAction)
        self.connect(self.transferList, SIGNAL("fileDropped"), self.addFileToList)
        self.setCentralWidget(self.transferList)
        self.transferList.setFocus()
    
    def updateTransferList(self, files):
        self.transferList.clear()
        self.sharedFiles = files
        self.fileIDs = files.keys()
        newSelection = -1
        for i, file in enumerate(self.sharedFiles[ID] for ID in self.fileIDs):
            widget = FileInfoWidget(self)
            self.updateFileWidget(widget, file)
            self.transferList.addItem(widget)
            if file.ID == self.selectedID:
                newSelection = i
        self.transferList.setSelectedIndex(newSelection)
    
    def updateFileWidget(self, widget, file):
        widget.setName(file.name)
        root, ext = os.path.splitext(file.name)
        icon = filetypes.from_mime_type_or_extension(file.mimeType, ext).icon(48)
        if icon and not icon.isNull():
            widget.setTypeIcon(icon)
        else:
            widget.setTypeIcon("mimetypes/gtk-file")
        if file.hasCopy(LOCAL):
            widget.setStatusIcon("actions/go-home", 0)
            if file.origin == LOCAL:
                localStatus = "Local copy is the original"
            else:
                localStatus = "Local copy is %.0f%% complete" % (file.completion(LOCAL) * 100.0)
        else:
            widget.setStatusIcon(None, 0)
            localStatus = ""
        widget.setStatusToolTip(localStatus, 0)
        if file.hasCopy(REMOTE):
            widget.setStatusIcon("categories/applications-internet", 2)
            if file.origin == REMOTE:
                remoteStatus = "Remote copy is the original"
            else:
                remoteStatus = "Remote copy is %.0f%% complete" % (file.completion(REMOTE) * 100.0)
        else:
            widget.setStatusIcon(None, 2)
            remoteStatus = ""
        widget.setStatusToolTip(remoteStatus, 2)
        if file.isReceiving:
            widget.setStatusIcon("actions/go-previous", 1)
            widget.setStatusToolTip("Receiving from peer", 1)
        elif file.isSending:
            widget.setStatusIcon("actions/go-next", 1)
            widget.setStatusToolTip("Sending to peer", 1)
        else:
            widget.setStatusIcon(None, 1)
            widget.setStatusToolTip("", 1)
        if file.origin == LOCAL:
            state = "Sent"
        elif file.origin == REMOTE:
            state = "Received"
        if file.transfer and (file.transfer.progress is not None):
            averageSpeed = formatSize(file.transfer.averageSpeed, "%s/s")
            if file.transfer.ended is not None:
                transferSize = formatSize(file.transfer.originalSize, "Size: %s")
                transferTime = "%s in %s (%s)" % (state,
                    formatDuration(file.transfer.totalSeconds), averageSpeed)
            else:
                transferSize = "%s / %s (%.1f%%)" % (
                    formatSize(file.transfer.completedSize),
                    formatSize(file.transfer.originalSize),
                    file.transfer.progress * 100.0)
                transferTime = "%s left (%s)" % (formatDuration(file.transfer.left), averageSpeed)
            widget.setTransferProgress(file.transfer.progress)
            widget.setTransferTime(transferTime)
            widget.setTransferSize(transferSize)
        else:
            widget.setTransferSize(formatSize(file.size, "Size: %s"))
    
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
            return connected and (file.origin == REMOTE)
        elif name == "pause":
            return connected and file.isTransfering
        elif name == "stop":
            return connected and file.isTransfering
        elif name == "open":
            return file.isComplete(LOCAL)
        else:
            return False
    
    def performAction(self, name, fileID=None):
        handler = getattr(self, "action_%s" % name)
        if not fileID or (not fileID in self.sharedFiles):
            fileID = self.selectedID
        handler(fileID)
    
    def performDefaultAction(self, index):
        fileID = self.fileIDs[index]
        if self.isActionAvailable("open", fileID):
            self.performAction("open", fileID)
        elif self.isActionAvailable("start", fileID):
            self.performAction("start", fileID)
    
    def action_connect(self, fileID):
        d = ConnectionDialog(self.app, self)
        d.exec_()
    
    def action_disconnect(self, fileID):
        self.app.disconnect()
    
    def action_add(self, fileID):
        dir = self.lastUsedFolder
        files = QFileDialog.getOpenFileNames(self, "Choose a file to open", dir, "All files (*.*)")
        if files.count() > 0:
            for file in files:
                path = unicode(file)
                self.addFileToList(path)
                self.lastUsedFolder = os.path.dirname(path)
    
    def addFileToList(self, path):
        type = filetypes.from_file(path)
        self.app.addFile(path, type.mimeType)
    
    def action_remove(self, fileID):
        if fileID is not None:
            self.app.removeFile(fileID)
    
    def action_start(self, fileID):
        if fileID is not None:
            file = self.app.files[fileID]
            defaultPath = os.path.join(self.lastUsedFolder, file.name)
            root, ext = os.path.splitext(file.name)
            if file.mimeType:
                description = filetypes.from_mime_type_or_extension(file.mimeType, ext).description
            else:
                description = "All files"
            type = "*" + ext
            dest = QFileDialog.getSaveFileName(self, "Choose where to receive the file",
                defaultPath, "%s (%s)" % (description, type))
            if dest:
                chosenPath = unicode(dest)
                self.app.startTransfer(self.selectedID, chosenPath)
                self.lastUsedFolder = os.path.dirname(chosenPath)
    
    def action_open(self, fileID):
        if fileID is not None:
            file = self.app.files[fileID]
            QDesktopServices.openUrl(QUrl.fromLocalFile(file.path))
    
    def initTimer(self):
        self.updateTimer = QTimer(self)
        self.updateTimer.setInterval(250)
        QObject.connect(self.updateTimer, SIGNAL('timeout()'), self.onTimerTicked)
    
    def onTimerTicked(self):
        self.app.updateTransferInfo()
    
    def onStateChanged(self):
        self.updateTransferList(self.app.files)
        self.updateStatusBar()
        self.updateToolBar()
        if (self.app.activeTransfers > 0) and not self.updateTimer.isActive():
            self.updateTimer.start()
        elif (self.app.activeTransfers == 0) and self.updateTimer.isActive():
            self.updateTimer.stop()
    
    def onFileUpdated(self, fileID):
        widget = None
        for i, widgetID in enumerate(self.fileIDs):
            if widgetID == fileID:
                widget = self.transferList[i]
                break
        if widget:
            file = self.app.files[fileID]
            self.updateFileWidget(widget, file)

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
