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
        self.branchWidth.setValue(self.logoWidget.logo.branchWidth)
        self.branchHeightText = QLabel("Branch height")
        self.branchHeight = QSpinBox()
        self.branchHeight.setMinimum(1)
        self.branchHeight.setMaximum(50)
        self.branchHeight.setValue(self.logoWidget.logo.branchSize)
        self.dotRadiusText = QLabel("Dot radius")
        self.dotRadius = QSpinBox()
        self.dotRadius.setMinimum(1)
        self.dotRadius.setMaximum(20)
        self.dotRadius.setValue(self.logoWidget.logo.dotRadius)
        self.borderThicknessText = QLabel("Border thickness")
        self.borderThickness = QSpinBox()
        self.borderThickness.setMinimum(1)
        self.borderThickness.setMaximum(20)
        self.borderThickness.setValue(self.logoWidget.logo.borderThickness)
        self.distanceText = QLabel("Distance from center")
        self.distance = QSpinBox()
        self.distance.setMinimum(0)
        self.distance.setMaximum(200)
        self.distance.setValue(self.logoWidget.logo.distance)
        self.inverseGradient = QCheckBox("Inverse color gradient")
        self.inverseGradient.setChecked(self.logoWidget.logo.inverseGradient)
        self.showAxes = QCheckBox("Show axes")
        self.showAxes.setChecked(self.logoWidget.showAxes)
        form = QFormLayout()
        form.addRow(self.branchWidthText, self.branchWidth)
        form.addRow(self.branchHeightText, self.branchHeight)
        form.addRow(self.dotRadiusText, self.dotRadius)
        form.addRow(self.borderThicknessText, self.borderThickness)
        form.addRow(self.distanceText, self.distance)
        form.addRow(self.inverseGradient)
        form.addRow(self.showAxes)
        vbox = QHBoxLayout(self)
        vbox.addWidget(self.logoWidget, 1)
        vbox.addLayout(form)
        QObject.connect(self.branchWidth, SIGNAL('valueChanged(int)'), self.logoWidget.setBranchWidth)
        QObject.connect(self.branchHeight, SIGNAL('valueChanged(int)'), self.logoWidget.setBranchHeight)
        QObject.connect(self.dotRadius, SIGNAL('valueChanged(int)'), self.logoWidget.setDotRadius)
        QObject.connect(self.borderThickness, SIGNAL('valueChanged(int)'), self.logoWidget.setBorderThickness)
        QObject.connect(self.distance, SIGNAL('valueChanged(int)'), self.logoWidget.setDistance)
        QObject.connect(self.inverseGradient, SIGNAL('toggled(bool)'), self.logoWidget.setInverseGradient)
        QObject.connect(self.showAxes, SIGNAL('toggled(bool)'), self.logoWidget.setShowAxes)

class LogoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.logo = logo.SparkLogo()
        self.showAxes = False
    
    def setBranchWidth(self, v):
        self.logo.branchWidth = v
        self.update()
    
    def setBranchHeight(self, v):
        self.logo.branchSize = v
        self.update()
    
    def setDotRadius(self, v):
        self.logo.dotRadius = v
        self.update()
    
    def setBorderThickness(self, v):
        self.logo.borderThickness = v
        self.update()
    
    def setDistance(self, v):
        self.logo.distance = v
        self.update()
    
    def setInverseGradient(self, v):
        self.logo.inverseGradient = v
        self.update()
    
    def setShowAxes(self, v):
        self.showAxes = v
        self.update()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # scale to widget size while preserving the aspect ratio
        dx, dy = float(p.device().width()), float(p.device().height())
        minN, maxN = -100.0, 100.0
        if dx > dy:
            yMin, yMax, yAmpl = minN, maxN, (maxN - minN)
            xAmpl = (1.0 + ((dx - dy) / dy)) * yAmpl
            xMin, xMax = -xAmpl / 2.0, xAmpl / 2.0
        else:
            xMin, xMax, xAmpl = minN, maxN, (maxN - minN)
            yAmpl = (1.0 + ((dy - dx) / dx)) * xAmpl
            yMin, yMax = -yAmpl / 2.0, yAmpl / 2.0
        p.scale(dx / xAmpl, dy / yAmpl)
        p.translate(-xMin, -yMin)
        if self.showAxes:
            p.drawLine(0.0, yMin, 0.0, yMax)
            p.drawLine(xMin, 0.0, xMax, 0.0)
        self.logo.draw(p)

if __name__ == "__main__":
    qApp = QApplication(sys.argv)
    w = TestLogoWidow()
    w.resize(800, 600)
    w.show()
    qApp.exec_()
