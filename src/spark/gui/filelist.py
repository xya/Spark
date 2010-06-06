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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from spark.gui.resource import iconPath

__all__ = ["FileList", "FileInfoWidget"]

class CustomList(QWidget):
    def __init__(self, parent=None):
        super(CustomList, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.oddColor = QPalette.Base
        self.evenColor = QPalette.AlternateBase
        self.setBackgroundRole(self.oddColor)
        self.setAutoFillBackground(True)
        self.items = []
        self.selectedIndex = -1
        layout = QVBoxLayout()
        layout.setMargin(0)
        layout.setSpacing(0)
        layout.addStretch()
        self.setLayout(layout)

    def addItem(self, widget):
        self.layout().insertWidget(self.layout().count() - 1, widget)
        self.items.append(widget)
        self.updateItems()
    
    def clear(self):
        """ Remove all the items from the list. """
        while True:
            item = self.layout().takeAt(0)
            if item is None:
                break
            # prevent the widget's parent from keeping it alive
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.layout().addStretch()
        self.items = []
        self.selectedIndex = -1
    
    def updateItems(self):
        for i in range(0, len(self.items)):
            self.updateItemPalette(i)
    
    def updateItemPalette(self, index):
        if index == self.selectedIndex:
            bgColor = QPalette.Highlight
            fgColor = QPalette.HighlightedText
        else:
            bgColor = (index % 2) and self.evenColor or self.oddColor
            fgColor = QPalette.WindowText
        item = self.items[index]
        item.setForegroundRole(fgColor)
        item.setBackgroundRole(bgColor)
    
    def findWidgetIndex(self, e):
        # the user might have clicked on a child's child widget
        # find the direct child widget
        widget = self.childAt(e.x(), e.y())
        while widget and not (widget.parentWidget() is self):
            widget = widget.parentWidget()
        if (widget is None) or not (widget in self.items):
            return -1
        else:
            return self.items.index(widget)
    
    def mousePressEvent(self, e):
        selected = self.findWidgetIndex(e)
        self.updateSelectedIndex(selected)
    
    def mouseDoubleClickEvent(self, e):
        item = self.findWidgetIndex(e)
        if item >= 0:
            self.emit(SIGNAL("itemActivated"), item)
    
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Up:
            selected = max(0, self.selectedIndex - 1)
        elif e.key() == Qt.Key_Down:
            selected = min(self.selectedIndex + 1, len(self.items) - 1)
        elif e.key() == Qt.Key_Home:
            selected = 0
        elif e.key() == Qt.Key_End:
            selected = len(self.items) - 1
        else:
            return
        self.updateSelectedIndex(selected)
    
    def updateSelectedIndex(self, newIndex):
        if newIndex != self.selectedIndex:
            self.selectedIndex = newIndex
            self.emit(SIGNAL("selectionChanged"), newIndex)
            self.updateItems()

class FileList(QWidget):
    """ Lets the user manipulate a list of files. """
    def __init__(self, parent=None):
        super(FileList, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.list = CustomList(self)
        self.setAcceptDrops(True)
        self.connect(self.list, SIGNAL("selectionChanged"), self.updateSelectedItem)
        self.connect(self.list, SIGNAL("itemActivated"), self, SIGNAL("itemActivated"))
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setFrameStyle(QFrame.NoFrame)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setWidget(self.list)
    
    def focusInEvent(self, e):
        self.list.setFocus()
    
    def minimumSizeHint(self):
        minHeight = minWidth = 0
        for item in self.list.items:
            minSize = item.minimumSizeHint()
            minWidth = max(minWidth, minSize.width())
            minHeight = max(minHeight, minSize.height())
        # some horizontal buffer for the scrollbar, and 2 items visible minimum
        return QSize(minWidth + 10, minHeight * 2)
    
    def sizeHint(self):
        return self.scrollArea.sizeHint()
    
    def resizeEvent(self, e):
        self.scrollArea.resize(e.size())
        self.ensureItemVisible(self.list.selectedIndex)
    
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
    
    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            for url in e.mimeData().urls():
                if url.scheme() == "file":
                    self.emit(SIGNAL("fileDropped"), unicode(url.toLocalFile()))
    
    def __getitem__(self, index):
        if index < 0 or index >= len(self.list.items):
            raise IndexError()
        return self.list.items[index]
    
    def selectedIndex(self):
        return self.list.selectedIndex
    
    def setSelectedIndex(self, index):
        self.list.updateSelectedIndex(index)
    
    def updateSelectedItem(self, index):
        self.ensureItemVisible(index)
        self.emit(SIGNAL("selectionChanged"), index)
    
    def ensureItemVisible(self, index):
        if index >= 0:
            w = self.list.items[index]
            self.scrollArea.ensureWidgetVisible(w, 0, 0)
    
    def addItem(self, widget):
        self.list.addItem(widget)
    
    def clear(self):
        self.list.clear()

class FileInfoWidget(QWidget):
    """ Shows the relevant information about a file or transfer to the user. """
    def __init__(self, parent=None):
        super(FileInfoWidget, self).__init__(parent)
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
        if isinstance(icon, basestring):
            self.typeIconSet = QIcon(iconPath(icon))
            self.typeIcon.setPixmap(self.typeIconSet.pixmap(48, 48))
        else:
            self.typeIcon.setPixmap(icon)
    
    def setStatusIcon(self, icon, index):
        statusIcon = self.statusIcons[index]
        if icon:
            statusIcon.setPixmap(QPixmap(iconPath(icon, 16)))
        else:
            statusIcon.setPixmap(QPixmap())
    
    def setStatusToolTip(self, text, index):
        statusIcon = self.statusIcons[index]
        statusIcon.setToolTip(text)
    
    def setTransferProgress(self, progress):
        if progress is not None:
            self.transferProgress.setValue(progress * 100.0)
            #FIXME: UI thread getting stuck here
            self.transferProgress.show()
        else:
            self.transferProgress.hide()
