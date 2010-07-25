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
import about

class TestLogoWidow(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Spark Logo")
        self.logoWidget = about.LogoWidget()
        self.exportToPng = QPushButton("Export to PNG")
        self.exportToSvg = QPushButton("Export to SVG")
        self.form = QFormLayout()
        self.addRangeOption("Number of branches", "branches", 3, 8)
        self.addRangeOption("Branch width", "branchWidth", 1, 50)
        self.addRangeOption("Branch height", "branchSize", 1, 200)
        self.addRangeOption("Dot radius", "dotRadius", 1, 200)
        self.addRangeOption("Border thickness", "borderThickness", 0, 100)
        self.addRangeOption("Distance from center", "distance", -200, 200)
        self.addRangeOption("Rotation", "rotation", -359, 359)
        self.addToggleOption("Show branch dots", "showBranchDots")
        self.addToggleOption("Round branches", "roundBranches")
        self.addToggleOption("Inverse color gradient", "inverseGradient")
        self.addRangeOption("Image export size", "imageSize", 16, 1024)
        self.form.addRow(self.exportToPng)
        self.form.addRow(self.exportToSvg)
        vbox = QHBoxLayout(self)
        vbox.addWidget(self.logoWidget, 1)
        vbox.addLayout(self.form)
        QObject.connect(self.exportToPng, SIGNAL('clicked()'), self.logoWidget.exportToPng)
        QObject.connect(self.exportToSvg, SIGNAL('clicked()'), self.logoWidget.exportToSvg)
    
    def addRangeOption(self, label, attribute, min, max):
        widget = QSpinBox()
        widget.setMinimum(min)
        widget.setMaximum(max)
        widget.setValue(self.getAttr(attribute))
        self.form.addRow(QLabel(label), widget)
        QObject.connect(widget, SIGNAL('valueChanged(int)'), self.setAttr(attribute))
    
    def addToggleOption(self, label, attribute):
        widget = QCheckBox(label)
        widget.setChecked(self.getAttr(attribute))
        self.form.addRow(widget)
        QObject.connect(widget, SIGNAL('toggled(bool)'), self.setAttr(attribute))
    
    def getAttr(self, attr):
        return getattr(self.logoWidget.logo, attr)
    
    def setAttr(self, attr):
        def fun(v):
            setattr(self.logoWidget.logo, attr, v)
            self.logoWidget.update()
        return fun

if __name__ == "__main__":
    qApp = QApplication(sys.argv)
    w = TestLogoWidow()
    w.resize(600, 400)
    w.show()
    qApp.exec_()
