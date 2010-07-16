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

def getRectangleCenter(r):
    return QPointF(r.left() + (r.width() / 2.0), r.top() + (r.height() / 2.0))

def getRadians(degrees):
    return ((degrees * math.pi) / 180.0)

def drawCircle(g, center, radius):
    circle = getCircleBounds(center, radius)
    circlePath = QPainterPath()
    circlePath.addEllipse(circle)
    g.drawPath(circlePath)

def drawCircleShadow(g, center, radius):
    circle = getCircleBounds(center, radius)
    circlePath = QPainterPath()
    circlePath.addEllipse(circle)
    gradient = QLinearGradient(circle.topLeft(), circle.bottomRight())
    gradient.setColorAt(0.0, QColor(0, 0, 0, 80))
    gradient.setColorAt(1.0, QColor(255, 255, 255, 64))
    g.fillPath(circlePath, QBrush(gradient))

class SparkLogo(object):
    def __init__(self):
        self.star = Star()
        self.star.distance = 70.0
        self.star.branchSize = 38.0
        self.star.branchWidth = 10.0
        self.star.dotRadius = 5.0
        self.star.update()
        self.borderThickness = 10.0
        self.alpha = 1.0
        self.borderColor = QColor("black")
        self.dotColor = QColor("silver")
        self.centerDotColor = QColor("gold")
        self.star.branches[0].branchColor = QColor("green")
        self.star.branches[1].branchColor = QColor("blueviolet")
        self.star.branches[2].branchColor = QColor("coral")
        self.star.branches[3].branchColor = QColor("red")
        self.star.branches[4].branchColor = QColor("blue")
        self.endBranchColor = QColor("white")
    
    @property
    def borderPen(self):
        return QPen(QBrush(self.borderColor), self.borderThickness / 10.0)
    
    def draw(self, painter):
        self.star.update()
        self.drawStar(painter, self.star)
    
    def drawStar(self, g, star):
        g.save()
        g.setPen(self.borderPen)
        g.setBrush(QBrush(self.dotColor))
        for i, branch in enumerate(star.branches):
            g.save()
            g.rotate(Star.angles[i])
            self.drawStarBranch(g, star, branch)
            outerPoint = branch.outerCenter
            secondPoint = barycenter(outerPoint, 2.0, QPointF(), 1.0)
            #drawCircle(g, outerPoint, star.dotRadius)
            #drawCircleShadow(g, outerPoint, star.dotRadius)
            #drawCircle(g, secondPoint, star.dotRadius)
            #drawCircleShadow(g, secondPoint, star.dotRadius)
            g.restore()
        g.setBrush(QBrush(self.centerDotColor))
        drawCircle(g, QPointF(), star.dotRadius)
        drawCircleShadow(g, QPointF(), star.dotRadius)
        g.restore()
        
    def drawStarBranch(self, g, star, branch):
        g.save()
        branchOutline = branch.outline
        branchBounds = branchOutline.boundingRect()
        g.translate(star.distance, 0.0)
        g.rotate(branch.angle - 180.0)
        gradient = QLinearGradient(QPointF(0.0, 0.0), branch.outerCenter)
        gradient.setColorAt(1.0, branch.branchColor)
        gradient.setColorAt(0.0, self.endBranchColor)
        g.setPen(self.borderPen)
        g.setBrush(QBrush(gradient))
        g.drawPath(branchOutline)
        g.restore()

class Star(object):
    angles = [270.0, 342.0, 54.0, 126.0, 198.0]
    def __init__(self):
        self.branches = [StarBranch() for i in range(0, 5)]
        self.distance = 0.0
        self.branchSize = 0.0
        self.branchWidth = 0.0
    
    def update(self):
        for i, branch in enumerate(self.branches):
            branch.angle = 360.0 / (2.0 * len(self.branches))
            branch.width = self.branchWidth
            branch.size = self.branchSize

class StarBranch(object):
    def __init__(self):
        self.width = self.size = 0.0
        self.angle = self.rotation = 0.0
        self.branchColor = QColor()
    
    @property
    def outerCenter(self):
        O, A, B, C, E, F = self.computePoints()
        return middle(middle(A, E), middle(B, F))
    
    def computePoints(self):
        origin = QPointF()
        alpha = getRadians(self.angle)
        c = self.width / math.sin(alpha)
        E = transform(origin, self.size, 0.0)
        F = transform(origin, self.size, -(alpha * 2.0))
        B = transform(F, self.width, Degrees90 -(alpha * 2.0))
        A = transform(E, self.width, -Degrees90)
        C = transform(origin, c, -alpha)
        return (origin, A, B, C, E, F)
    
    @property
    def outline(self):
        p = QPainterPath()
        O, A, B, C, E, F = self.computePoints()
        p.moveTo(O)
        p.lineTo(F)
        C2 = getCircleBounds(middle(B, F), self.width / 2.0)
        #p.arcTo(C2, 90.0 - self.angle, -180.0)
        p.lineTo(B)
        #p.quadTo(middle(F, B), B)
        p.lineTo(C)
        p.lineTo(A)
        C1 = getCircleBounds(middle(A, E), self.width / 2.0)
        #p.arcTo(C1, 270.0 + self.angle, -180.0)
        p.lineTo(E)
        p.lineTo(O)
        p.closeSubpath()
        return p