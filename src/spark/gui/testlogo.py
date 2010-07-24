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
        self.form.addRow(self.exportToSvg)
        vbox = QHBoxLayout(self)
        vbox.addWidget(self.logoWidget, 1)
        vbox.addLayout(self.form)
        QObject.connect(self.exportToSvg, SIGNAL('clicked()'), self.logoWidget.exportToSvg)
    
    def addRangeOption(self, label, attribute, min, max):
        widget = QSpinBox()
        widget.setMinimum(min)
        widget.setMaximum(max)
        widget.setValue(self.logoWidget.getAttr(attribute))
        self.form.addRow(QLabel(label), widget)
        QObject.connect(widget, SIGNAL('valueChanged(int)'), self.logoWidget.setAttr(attribute))
    
    def addToggleOption(self, label, attribute):
        widget = QCheckBox(label)
        widget.setChecked(self.logoWidget.getAttr(attribute))
        self.form.addRow(widget)
        QObject.connect(widget, SIGNAL('toggled(bool)'), self.logoWidget.setAttr(attribute))

class LogoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.logo = logo.SparkLogo()
    
    def getAttr(self, attr):
        return getattr(self.logo, attr)
    
    def setAttr(self, attr):
        def fun(v):
            setattr(self.logo, attr, v)
            self.update()
        return fun
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # scale to widget size while preserving the aspect ratio
        size = QSizeF(p.device().width(), p.device().height())
        bounds = self.computeViewport(size, -100.0, 100.0)
        p.setTransform(self.viewportTransform(size, bounds))
        self.logo.draw(p)
    
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
        self.logo.draw(p)
        p.end()
    
    def settingsMap(self):
        l = self.logo
        return {"branches": l.branches,
                "branchWidth": l.branchWidth,
                "branchHeight": l.branchSize,
                "dotRadius": l.dotRadius,
                "borderThickness": l.borderThickness,
                "distance": l.distance,
                "rotation": l.rotation,
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

if __name__ == "__main__":
    qApp = QApplication(sys.argv)
    w = TestLogoWidow()
    w.resize(800, 600)
    w.show()
    qApp.exec_()
