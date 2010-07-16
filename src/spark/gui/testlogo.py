#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Pierre-André Saulais <pasaulais@free.fr>
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
import sys
import logo

class TestLogoWidow(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Spark Logo")
        self.logoWidget = LogoWidget()
        self.branchWidthText = QLabel("Branch width")
        self.branchWidth = QSpinBox()
        self.branchWidth.setMinimum(1)
        self.branchWidth.setMaximum(50)
        self.branchWidth.setValue(self.logoWidget.logo.star.branchWidth)
        self.branchHeightText = QLabel("Branch height")
        self.branchHeight = QSpinBox()
        self.branchHeight.setMinimum(1)
        self.branchHeight.setMaximum(50)
        self.branchHeight.setValue(self.logoWidget.logo.star.branchSize)
        self.radiusText = QLabel("Radius")
        self.radius = QSpinBox()
        self.radius.setMinimum(1)
        self.radius.setMaximum(200)
        self.radius.setValue(self.logoWidget.logo.star.radius)
        form = QFormLayout()
        form.addRow(self.branchWidthText, self.branchWidth)
        form.addRow(self.branchHeightText, self.branchHeight)
        form.addRow(self.radiusText, self.radius)
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.logoWidget, 1)
        vbox.addLayout(form)
        QObject.connect(self.branchWidth, SIGNAL('valueChanged(int)'), self.logoWidget.setBranchWidth)
        QObject.connect(self.branchHeight, SIGNAL('valueChanged(int)'), self.logoWidget.setBranchHeight)
        QObject.connect(self.radius, SIGNAL('valueChanged(int)'), self.logoWidget.setRadius)

class LogoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.logo = logo.SparkLogo()
    
    def setBranchWidth(self, v):
        self.logo.star.branchWidth = v
        self.update()
    
    def setBranchHeight(self, v):
        self.logo.star.branchSize = v
        self.update()
    
    def setRadius(self, v):
        self.logo.star.radius = v
        self.update()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # scale to widget size while preserving the aspect ratio
        dx, dy = p.device().width(), p.device().height()
        dn = min(dx, dy)
        offsetX = (dx - dn) / 2.0
        offsetY = (dy - dn) / 2.0
        p.translate(offsetX, offsetY)
        p.scale(dn / 200.0, dn / 200.0)
        self.logo.draw(p)
        #self.logo.star.update()
        #self.logo.drawStarBranch(p, self.logo.star, self.logo.star.branches[0])

if __name__ == "__main__":
    qApp = QApplication(sys.argv)
    w = TestLogoWidow()
    w.resize(800, 600)
    w.show()
    qApp.exec_()
