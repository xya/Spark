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
from PyQt4.QtCore import QPointF, QRectF, QSize
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
        self.dotRadius = 5.0
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
        circle = getCircleBounds(center, self.dotRadius)
        path = QPainterPath()
        path.addEllipse(circle)
        return path
    
    def drawDot(self, g, center=QPointF()):
        circlePath = self.dotPath(center)
        g.drawPath(circlePath)
        circle = getCircleBounds(center, self.dotRadius)
        gradient = QLinearGradient(circle.topLeft(), circle.bottomRight())
        gradient.setColorAt(0.0, QColor(0, 0, 0, 80))
        gradient.setColorAt(1.0, QColor(255, 255, 255, 64))
        g.fillPath(circlePath, QBrush(gradient))
    
    def draw(self, g):
        g.save()
        g.setPen(self.borderPen)
        g.setBrush(QBrush(self.dotColor))
        for i in range(0, self.branches):
            g.save()
            g.rotate(self.angles[i])
            self.drawStarBranch(g, i)
            outerPoint = self.branchOuterCenter
            secondPoint = barycenter(outerPoint, 2.0, QPointF(), 1.0)
            #self.drawDot(g, outerPoint)
            #self.drawDot(g, secondPoint)
            g.restore()
        g.setBrush(QBrush(self.centerDotColor))
        self.drawDot(g)
        g.restore()
        
    def drawStarBranch(self, g, i):
        g.save()
        g.translate(self.distance, 0.0)
        g.rotate(self.branchAngle - 180.0)
        gradient = QLinearGradient(QPointF(0.0, 0.0), self.branchOuterCenter)
        start, end = self.branchColor[i], self.endBranchColor
        if self.inverseGradient:
            gradient.setColorAt(0.0, end)
            gradient.setColorAt(1.0, start)
        else:
            gradient.setColorAt(0.0, start)
            gradient.setColorAt(1.0, end)
        g.setPen(self.borderPen)
        g.setBrush(QBrush(gradient))
        g.drawPath(self.branchOutline)
        g.restore()
    
    def boundingPath(self):
        # create a painting path that the union of all paths in the logo
        outline = self.branchOutline
        combine = QPainterPath()
        for i in range(0, self.branches):
            t = QTransform()
            t.rotate(self.angles[i])
            t.translate(self.distance, 0.0)
            t.rotate(self.branchAngle - 180.0)
            path = t.map(outline)
            combine = combine.united(path)
        # center dot
        combine = combine.united(self.dotPath(QPointF(0.0, 0.0)))
        stroker = QPainterPathStroker()
        stroker.setWidth(self.borderThickness / 10.0)
        return stroker.createStroke(combine)
    
    @property
    def branchOuterCenter(self):
        O, A, B, C, E, F = self.computeBranchPoints()
        return middle(middle(A, E), middle(B, F))
    
    def computeBranchPoints(self):
        origin = QPointF()
        alpha = getRadians(self.branchAngle)
        c = self.branchWidth / math.sin(alpha)
        E = transform(origin, self.branchSize, 0.0)
        F = transform(origin, self.branchSize, -(alpha * 2.0))
        B = transform(F, self.branchWidth, Degrees90 -(alpha * 2.0))
        A = transform(E, self.branchWidth, -Degrees90)
        C = transform(origin, c, -alpha)
        return (origin, A, B, C, E, F)
    
    @property
    def branchOutline(self):
        p = QPainterPath()
        O, A, B, C, E, F = self.computeBranchPoints()
        p.moveTo(O)
        p.lineTo(F)
        if self.roundBranches:
            C2 = getCircleBounds(middle(B, F), self.branchWidth / 2.0)
            p.arcTo(C2, 180.0 - self.branchAngle, -180.0)
        else:
            p.lineTo(B)
        p.lineTo(C)
        p.lineTo(A)
        if self.roundBranches:
            C1 = getCircleBounds(middle(A, E), self.branchWidth / 2.0)
            p.arcTo(C1, 90.0, -180.0)
        else:
            p.lineTo(E)
        p.lineTo(O)
        p.closeSubpath()
        return p