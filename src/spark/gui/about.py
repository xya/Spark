# -*- coding: utf-8 -*-
#
# Copyright (C) 2004-2007, 2010 Pierre-André Saulais <pasaulais@free.fr>
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

import math
from PyQt4.QtCore import QPointF, QRectF, QSize, QSizeF, Qt, SIGNAL, SLOT
from PyQt4.QtGui import *

class AboutWindow(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.title = QLabel(u"Spark 0.0.4")
        titleFont = self.title.font()
        titleFont.setWeight(QFont.Bold)
        titleFont.setPointSize(18)
        self.title.setFont(titleFont)
        self.subtitle = QLabel(u"A simple file-transfer tool")
        subtitleFont = self.subtitle.font()
        subtitleFont.setPointSize(12)
        self.subtitle.setFont(subtitleFont)
        self.author = QLabel(u"Pierre-Adré Saulais <pasaulais@free.fr>")
        authorFont = self.author.font()
        authorFont.setPointSize(10)
        self.author.setFont(authorFont)
        self.copyright = QLabel(u"Copyright (c) 2009-2010")
        copyrightFont = self.copyright.font()
        copyrightFont.setPointSize(10)
        self.copyright.setFont(copyrightFont)
        self.closeButton = QPushButton(u"Close")
        self.logoWidget = LogoWidget()
        self.logoWidget.logo.branchWidth = 18
        self.logoWidget.logo.branchSize = 50
        self.logoWidget.logo.borderThickness = 20.0
        self.logoWidget.logo.distance = 0.0
        self.logoWidget.logo.rotation = 23.0
        self.logoWidget.logo.showBranchDots = False
        self.logoWidget.setFixedSize(QSize(96, 96))
        self.initLayout()
        self.setWindowTitle("About Spark")
        self.setWindowFlags(Qt.Dialog)
        self.setFixedSize(self.sizeHint())
        QWidget.connect(self.closeButton, SIGNAL("clicked()"), self, SLOT("close()"))
    
    def initLayout(self):
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.closeButton, 0, Qt.AlignHCenter)
        
        infoLayout = QVBoxLayout()
        infoLayout.addWidget(self.title, 0, Qt.AlignHCenter)
        infoLayout.addWidget(self.subtitle, 0, Qt.AlignHCenter)
        infoLayout.addWidget(self.author, 0, Qt.AlignHCenter)
        infoLayout.addWidget(self.copyright, 0, Qt.AlignHCenter)
        infoLayout.setSpacing(0)
        
        hLayout = QHBoxLayout()
        hLayout.addWidget(self.logoWidget, 0, Qt.AlignCenter)
        hLayout.addLayout(infoLayout)
        hLayout.setSpacing(20)
        
        mainLayout = QVBoxLayout(self)
        mainLayout.addLayout(hLayout)
        mainLayout.addLayout(buttonLayout)
        mainLayout.setSpacing(15)

class LogoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.logo = SparkLogo()
    
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # scale to widget size while preserving the aspect ratio
        size = QSizeF(p.device().width(), p.device().height())
        viewport = self.viewportFromSize(size)
        p.setTransform(self.viewportTransform(size, viewport))
        self.logo.draw(p)
    
    def exportToSvg(self):
        size = self.size()
        viewport = self.viewportFromSize(QSizeF(size))
        transform = self.viewportTransform(QSizeF(size), viewport)
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
        svg.setViewBox(transform.mapRect(viewport))
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
    
    def viewportFromSize(self, size):
        bounds = self.logo.boundingPath().boundingRect()
        if bounds.width() > bounds.height():
            return self.computeViewport(size, bounds.left(), bounds.right())
        else:
            return self.computeViewport(size, bounds.top(), bounds.bottom())
    
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

Degrees90 = (math.pi * 0.5)
Degrees180 = math.pi
Degrees270 = (math.pi * 1.5)
Degrees360 = (math.pi * 2.0)

def transform(origin, length, angle):
    return QPointF(origin.x() + (length * math.cos(angle)), origin.y() + (length * math.sin(angle)))

def middle(pointA, pointB):
    return barycenter(pointA, 1, pointB, 1)

def barycenter(pointA, a, pointB, b):
    ab = (a + b)
    if ab == 0.0:
        raise ValueError()
    else:
        return QPointF(((a * pointA.x()) + (b * pointB.x())) / ab, 
            ((a * pointA.y()) + (b * pointB.y())) / ab)

def getCircleBounds(center, radius):
    return QRectF(center.x() - radius, center.y() - radius, 2.0 * radius, 2.0 * radius)

def getRadians(degrees):
    return ((degrees * math.pi) / 180.0)

class SparkLogo(object):
    def __init__(self):
        self.distance = 70.0
        self.rotation = 0.0
        self.branchSize = 38.0
        self.branchWidth = 10.0
        self.dotRadius = 50.0
        self.borderThickness = 10.0
        self.roundBranches = False
        self.branches = 4
        self.showBranchDots = True
        self.borderColor = QColor("black")
        self.dotColor = QColor("silver")
        self.centerDotColor = QColor("gold")
        self.branchColors = [QColor("limegreen"),
                            QColor("tomato"),
                            QColor("dodgerblue"),
                            QColor("darkorange"),
                            QColor("dodgerblue")]
        self.branchColors = [QColor("dodgerblue"),
                            QColor("darkorange"),
                            QColor("limegreen"),
                            QColor("tomato")]
        self.branchColors = [QColor("dodgerblue"),
                            QColor("limegreen"),
                            QColor("dodgerblue"),
                            QColor("darkorange")]
        self.endBranchColor = QColor("white")
        self.inverseGradient = True
    
    @property
    def branchAngle(self):
        return 360.0 / (self.branches * 2.0)
    
    def branchRotation(self, index):
        return 360.0 / self.branches * (index - 0.25)
    
    def branchColor(self, index):
        return self.branchColors[index % 4]
    
    @property
    def borderPen(self):
        if self.borderThickness > 0.0:
            return QPen(QBrush(self.borderColor), self.borderThickness / 10.0)
        return Qt.NoPen
    
    def dotPath(self, center):
        circle = getCircleBounds(center, self.dotRadius / 10.0)
        path = QPainterPath()
        path.addEllipse(circle)
        return path
    
    def drawDot(self, g, center=QPointF()):
        circlePath = self.dotPath(center)
        g.drawPath(circlePath)
        circle = getCircleBounds(center, self.dotRadius / 10.0)
        gradient = QLinearGradient(circle.topLeft(), circle.bottomRight())
        gradient.setColorAt(0.0, QColor(0, 0, 0, 80))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 64))
        g.fillPath(circlePath, QBrush(gradient))
    
    def draw(self, g):
        g.save()
        branch = LogoBranch(self)
        g.rotate(self.rotation)
        for i in range(0, self.branches):
            g.save()
            g.rotate(self.branchRotation(i))
            g.translate(self.distance, 0.0)
            self.drawStarBranch(g, i, branch)
            g.restore()
        g.setPen(self.borderPen)
        g.setBrush(QBrush(self.centerDotColor))
        self.drawDot(g)
        g.restore()
        
    def drawStarBranch(self, g, i, branch):
        g.save()
        g.rotate(self.branchAngle - 180.0)
        # draw branch with color gradient
        gradient = QLinearGradient(branch.origin, branch.outerPoint)
        start, end = self.branchColor(i), self.endBranchColor
        if self.inverseGradient:
            gradient.setColorAt(0.0, end)
            gradient.setColorAt(0.1, end)
            gradient.setColorAt(1.0, start)
        else:
            gradient.setColorAt(0.0, start)
            gradient.setColorAt(0.9, end)
            gradient.setColorAt(1.0, end)
        g.setPen(self.borderPen)
        g.setBrush(QBrush(gradient))
        g.drawPath(branch.outline)
        # draw dots
        if self.showBranchDots:
            g.setPen(self.borderPen)
            g.setBrush(QBrush(self.dotColor))
            for dotPoint in branch.dots:
                self.drawDot(g, dotPoint)
        g.restore()
    
    def boundingPath(self):
        # create a painting path that is the union of all paths in the logo
        branch = LogoBranch(self)
        combine = QPainterPath()
        for i in range(0, self.branches):
            t = QTransform()
            t.rotate(self.branchRotation(i))
            t.translate(self.distance, 0.0)
            t.rotate(self.branchAngle - 180.0)
            branchPath = t.map(branch.outline)
            combine = combine.united(branchPath)
            if self.showBranchDots:
                for dotPoint in branch.dots:
                    combine = combine.united(t.map(self.dotPath(dotPoint)))
        # center dot
        combine = combine.united(self.dotPath(QPointF(0.0, 0.0)))
        if self.rotation != 0.0:
            t2 = QTransform()
            t2.rotate(self.rotation)
            combine = t2.map(combine)
        stroker = QPainterPathStroker()
        stroker.setWidth(self.borderThickness / 10.0)
        return stroker.createStroke(combine)
    
class LogoBranch(object):
    def __init__(self, logo):
        angle, bw, bs = logo.branchAngle, logo.branchWidth, logo.branchSize
        self.sym = QTransform()
        self.sym.rotate((90.0 - angle) * 2.0)
        self.sym.scale(-1.0, 1.0)
        alpha = getRadians(angle)
        self.origin = QPointF(0.0, 0.0)
        self.pointA = QPointF(bs, 0.0)
        self.pointB = QPointF(bs, -bw)
        self.pointI = middle(self.pointA, self.pointB)
        self.pointC = QPointF(bw / math.tan(alpha), -bw)
        self.outerPoint = middle(self.pointI, self.sym.map(self.pointI))
        #self.outerPoint = middle(self.pointB, self.sym.map(self.pointB))
        self.curveRect = QRectF(bs - bw, -bw, bw, bw)
        self.outline = self._createPath(logo.roundBranches)
        self.dots = [self.outerPoint]#, barycenter(self.outerPoint, 2.0, self.origin, 1.0)]
    
    def _createPath(self, roundBranches):
        # create the first half of the branch
        p = QPainterPath()
        p.moveTo(self.origin)
        if roundBranches:
            p.arcTo(self.curveRect, -90.0, 180.0)
        else:
            p.lineTo(self.pointA)
            p.lineTo(self.pointB)
        p.lineTo(self.pointC)
        # create the other half of the branch by symmetry
        p.connectPath(self.sym.map(p.toReversed()))
        p.closeSubpath()
        return p