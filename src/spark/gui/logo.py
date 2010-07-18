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
from PyQt4.QtCore import QPointF, QRectF, QSize, Qt
from PyQt4.QtGui import *

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
        self.branchSize = 38.0
        self.branchWidth = 10.0
        self.dotRadius = 50.0
        self.borderThickness = 10.0
        self.roundBranches = False
        self.branches = 5
        self.branchAngle = 360.0 / (self.branches * 2.0)
        self.angles = [360.0 / self.branches * (i - 0.25)
                       for i in range(1, self.branches + 1)]
        self.borderColor = QColor("black")
        self.dotColor = QColor("silver")
        self.centerDotColor = QColor("gold")
        self.branchColor = [QColor("coral"), QColor("red"), QColor("blue"),
                            QColor("green"), QColor("blueviolet")]
        self.endBranchColor = QColor("white")
        self.inverseGradient = True
    
    @property
    def borderPen(self):
        return QPen(QBrush(self.borderColor), self.borderThickness / 10.0)
    
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
        for i in range(0, self.branches):
            g.save()
            g.rotate(self.angles[i])
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
        gradient = QLinearGradient(QPointF(0.0, 0.0), branch.outerCenter)
        start, end = self.branchColor[i], self.endBranchColor
        if self.inverseGradient:
            gradient.setColorAt(0.0, end)
            gradient.setColorAt(1.0, start)
        else:
            gradient.setColorAt(0.0, start)
            gradient.setColorAt(1.0, end)
        g.setPen(self.borderPen)
        g.setBrush(QBrush(gradient))
        g.drawPath(branch.outline)
        # draw dots
        g.setPen(self.borderPen)
        g.setBrush(QBrush(self.dotColor))
        outerPoint = branch.outerCenter
        secondPoint = barycenter(outerPoint, 2.0, QPointF(), 1.0)
        #self.drawDot(g, outerPoint)
        #self.drawDot(g, secondPoint)
        g.restore()
    
    def boundingPath(self):
        # create a painting path that the union of all paths in the logo
        branch = LogoBranch(self)
        combine = QPainterPath()
        for i in range(0, self.branches):
            t = QTransform()
            t.rotate(self.angles[i])
            t.translate(self.distance, 0.0)
            t.rotate(self.branchAngle - 180.0)
            branchPath = t.map(branch.outline)
            combine = combine.united(branchPath)
            #dotPath = t.map(self.dotPath(branch.outerCenter))
            #combine = combine.united(dotPath)
        # center dot
        combine = combine.united(self.dotPath(QPointF(0.0, 0.0)))
        stroker = QPainterPathStroker()
        stroker.setWidth(self.borderThickness / 10.0)
        return stroker.createStroke(combine)
    
class LogoBranch(object):
    def __init__(self, logo):
        angle, bw, bs = logo.branchAngle, logo.branchWidth, logo.branchSize
        self.sym = QTransform()
        self.sym.rotate(-90.0 + angle)
        self.sym.scale(1.0, -1.0)
        self.sym.rotate(90.0 - 2.0 * angle)
        alpha = getRadians(angle)
        self.pointO = QPointF(0.0, 0.0)
        self.pointE = QPointF(bs, 0.0)
        self.pointA = QPointF(bs, -bw)
        self.pointI = middle(self.pointA, self.pointE)
        self.pointC = QPointF(bw / math.tan(alpha), -bw)
        #self.outerCenter = middle(self.pointI, self.sym.map(self.pointI))
        self.outerCenter = middle(self.pointA, self.sym.map(self.pointA))
        self.curveRect = QRectF(bs - bw, -bw, bw, bw)
        self.outline = self._createPath(logo.roundBranches)
    
    def _createPath(self, roundBranches):
        # create the first half of the branch
        p = QPainterPath()
        p.moveTo(self.pointO)
        if roundBranches:
            p.arcTo(self.curveRect, -90.0, 180.0)
        else:
            p.lineTo(self.pointE)
            p.lineTo(self.pointA)
        p.lineTo(self.pointC)
        # create the other half of the branch by symmetry
        p.connectPath(self.sym.map(p.toReversed()))
        p.closeSubpath()
        return p