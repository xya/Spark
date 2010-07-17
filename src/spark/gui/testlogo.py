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
try:
    from PyQt4.QtSvg import QSvgGenerator
except ImportError:
    QSvgGenerator = None
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
        self.borderThickness.setMaximum(40)
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
        self.exportToSvg = QPushButton("Export to SVG")
        form = QFormLayout()
        form.addRow(self.branchWidthText, self.branchWidth)
        form.addRow(self.branchHeightText, self.branchHeight)
        form.addRow(self.dotRadiusText, self.dotRadius)
        form.addRow(self.borderThicknessText, self.borderThickness)
        form.addRow(self.distanceText, self.distance)
        form.addRow(self.inverseGradient)
        form.addRow(self.showAxes)
        form.addRow(self.exportToSvg)
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
        QObject.connect(self.exportToSvg, SIGNAL('clicked()'), self.logoWidget.exportToSvg)

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
        size = QSizeF(p.device().width(), p.device().height())
        bounds = self.computeViewport(size, -100.0, 100.0)
        p.setTransform(self.viewportTransform(size, bounds))
        self.drawLogo(p, bounds)
    
    def exportToSvg(self):
        size = self.size()
        vpBounds = self.computeViewport(QSizeF(size), -100.0, 100.0)
        transform = self.viewportTransform(QSizeF(size), vpBounds)
        fileName = QFileDialog.getSaveFileName(self, "Save logo", "", "SVG files (*.svg)")
        if not fileName or fileName.isEmpty():
            return
        svg = QSvgGenerator()
        svg.setFileName(fileName)
        svg.setTitle("Spark Logo")
        # save settings as description
        settings = self.settingsMap()
        settingsText = "{%s}" % ", ".join(["'%s': %s" % (k, repr(v))
                                           for (k, v) in settings.iteritems()])
        svg.setDescription("This picture was generated to be a Spark logo.\n"
            "The settings used were: %s" % settingsText)
        # crop the logo to its bounding box
        logoBounds = self.logo.boundingPath().boundingRect()
        svg.setViewBox(transform.mapRect(logoBounds))
        svg.setSize(size)
        p = QPainter()
        p.begin(svg)
        p.setTransform(transform)
        self.drawLogo(p, vpBounds)
        p.end()
    
    def settingsMap(self):
        l = self.logo
        return {"branchWidth": l.branchWidth,
                "branchHeight": l.branchSize,
                "dotRadius": l.dotRadius,
                "borderThickness": l.borderThickness,
                "distance": l.distance,
                "inverseGradient": l.inverseGradient}
    
    def computeViewport(self, size, minN, maxN):
        if size.width() > size.height():
            yMin, yAmpl = minN, (maxN - minN)
            xAmpl = (1.0 + ((size.width() - size.height()) / size.height())) * yAmpl
            xMin = -xAmpl / 2.0
        else:
            xMin, xAmpl = minN, (maxN - minN)
            yAmpl = (1.0 + ((size.height() - size.width()) / size.width())) * xAmpl
            yMin = -yAmpl / 2.0
        return QRectF(xMin, yMin, xAmpl, yAmpl)
    
    def viewportTransform(self, size, bounds):
        t = QTransform()
        t.scale(size.width() / bounds.width(), size.height() / bounds.height())
        t.translate(-bounds.left(), -bounds.top())
        return t
    
    def drawLogo(self, p, bounds):
        if self.showAxes:
            p.drawLine(0.0, bounds.top(), 0.0, bounds.bottom())
            p.drawLine(bounds.left(), 0.0, bounds.right(), 0.0)
        self.logo.draw(p)

if __name__ == "__main__":
    qApp = QApplication(sys.argv)
    w = TestLogoWidow()
    w.resize(800, 600)
    w.show()
    qApp.exec_()
