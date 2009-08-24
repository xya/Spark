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
        self.fileList = SharedFileList()
        self.fileList.addFile("Report.pdf", "Size: 3 MiB", "mimetypes/gnome-mime-application-pdf",
                   None, None, "categories/applications-internet")
        self.fileList.addFile("Spark-0.1_noarch.deb", "Size: 1 MiB", "mimetypes/deb",
                   "actions/go-home", None, "categories/applications-internet")
        self.fileList.files[1].setTransferTime("Received in 10 secondes (100 KiB/s)")
        self.fileList.addFile("SeisRoX-2.0.9660.exe", "Received 5.25 MiB out of 22 MiB (24.5%)", "mimetypes/exec",
                   "actions/go-home", "actions/go-previous", "categories/applications-internet")
        self.fileList.files[2].setTransferProgress(24)
        self.fileList.files[2].setTransferTime("5 minutes left (50 KiB/s)")
        self.fileList.addFile("TestArchive.zip", "Size: 117 MiB", "mimetypes/zip",
                   "actions/go-home", None, None)
        self.fileList.addSpace()
        self.connect(self.fileList, SIGNAL("selectionChanged"), self.updateSelectedFile)
        self.scrollArea = QScrollArea()
        self.scrollArea.setFrameStyle(QFrame.NoFrame)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setMinimumWidth(540)
        self.scrollArea.setWidget(self.fileList)
        self.setCentralWidget(self.scrollArea)
        self.fileList.setFocus()
    
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
        if index >= 0:
            w = self.fileList.files[index]
            self.scrollArea.ensureWidgetVisible(w, 0, 0)

# TODO: rename to CustomFileList
#       class SharedFileList wraps it + scroll area
class SharedFileList(QWidget):
    def __init__(self, parent=None):
        super(SharedFileList, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        pal = self.palette()
        self.oddColor = pal.color(QPalette.Base)
        self.evenColor = pal.color(QPalette.AlternateBase)
        pal.setColor(QPalette.Window, self.oddColor)
        self.setAutoFillBackground(True)
        self.files = []
        self.selectedIndex = -1
        layout = QVBoxLayout()
        layout.setMargin(0)
        layout.setSpacing(0)
        self.setLayout(layout)
    
    def addFile(self, name, size, icon, *args):
        widget = SharedFileWidget(self)
        widget.setName(name)
        widget.setTransferSize(size)
        widget.setTypeIcon(icon)
        for i, icon in enumerate(args):
            widget.setStatusIcon(icon, i)
        self.layout().addWidget(widget)
        self.files.append(widget)
        self.updateItems()
    
    def addSpace(self):
        self.layout().addStretch()
    
    def updateItems(self):
        for i in range(0, len(self.files)):
            self.updateItemPalette(i)
    
    def updateItemPalette(self, index):
        appPal = QApplication.palette()
        if index == self.selectedIndex:
            bgColor = appPal.color(QPalette.Highlight)
            fgColor = appPal.color(QPalette.HighlightedText)
        else:
            bgColor = (index % 2) and self.evenColor or self.oddColor
            fgColor = appPal.color(QPalette.WindowText)
        item = self.files[index]
        pal = item.palette()
        pal.setColor(QPalette.Window, bgColor)
        pal.setColor(QPalette.WindowText, fgColor)
        item.updatePalette(pal)
    
    def mousePressEvent(self, e):
        # the user might have clicked on a child's child widget
        # find the direct child widget
        widget = self.childAt(e.x(), e.y())
        while widget and not (widget.parentWidget() is self):
            widget = widget.parentWidget()
        if (widget is None) or not (widget in self.files):
            selected = -1
        else:
            selected = self.files.index(widget)
        self.updateSelectedIndex(selected)
    
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Up:
            selected = max(0, self.selectedIndex - 1)
        elif e.key() == Qt.Key_Down:
            selected = min(self.selectedIndex + 1, len(self.files) - 1)
        elif e.key() == Qt.Key_Home:
            selected = 0
        elif e.key() == Qt.Key_End:
            selected = len(self.files) - 1
        else:
            return
        self.updateSelectedIndex(selected)
    
    def updateSelectedIndex(self, newIndex):
        if newIndex != self.selectedIndex:
            self.selectedIndex = newIndex
            self.emit(SIGNAL("selectionChanged"), newIndex)
            self.updateItems()

class SharedFileWidget(QWidget):
    def __init__(self, parent=None):
        super(SharedFileWidget, self).__init__(parent)
        self.setAutoFillBackground(True)
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
        grid.setMargin(8)
        grid.addWidget(self.typeIcon, 0, 0, Qt.AlignCenter)
        grid.addLayout(content, 0, 1, Qt.AlignVCenter)
        grid.addLayout(status, 1, 0)
        grid.addWidget(self.transferProgress, 1, 1)
        self.setLayout(grid)
    
    def updatePalette(self, newPalette):
        self.fileName.setPalette(newPalette)
        self.transferSize.setPalette(newPalette)
        self.transferTime.setPalette(newPalette)
        self.repaint()
    
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