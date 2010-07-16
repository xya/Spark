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

def drawCircleShadow(g, center, radius, angle, alpha):
    circle = getCircleBounds(center, radius)
    circlePath = QPainterPath()
    circlePath.addEllipse(circle)
    # still need to rotate by angle degrees
    gradient = QLinearGradient(circle.topLeft(), circle.bottomRight())
    gradient.setColorAt(0.0, QColor(0, 0, 0, 80))
    gradient.setColorAt(1.0, QColor(255, 255, 255, 64))
    g.fillPath(circlePath, QBrush(gradient))

class SparkLogo(object):
    def __init__(self):
        self.star = Star()
        self.star.center = QPointF(100, 100)
        self.star.radius = 70.0
        self.star.branchSize = 20.0
        self.star.branchWidth = 10.0
        self.star.update()
        self.size = QSize(200, 200)
        self.borderThickness = 2.0
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
        return QPen(QBrush(self.borderColor), self.borderThickness)
    
    def draw(self, painter):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        #self.star.center = getRectangleCenter(QRectF(0.0, 0.0,
        #    painter.device().width(), painter.device().height()))
        self.star.update()
        self.drawStar(painter, self.star)
        painter.restore()
    
    def drawStar(self, g, star):
        g.save()
        g.setPen(self.borderPen)
        g.setBrush(QBrush(self.dotColor))
        for branch in star.branches:
            self.drawStarBranch(g, star, branch)
            secondPoint = barycenter(branch.outerCenter, 2.0, star.center, 1.0)
            drawCircle(g, branch.outerCenter, branch.width / 2.0)
            drawCircleShadow(g, branch.outerCenter, branch.width / 2.0, branch.rotation, self.alpha)
            drawCircle(g, secondPoint, branch.width / 2.0)
            drawCircleShadow(g, secondPoint, branch.width / 2.0, branch.rotation, self.alpha)
        g.setBrush(QBrush(self.centerDotColor))
        drawCircle(g, star.center, star.branchWidth / 2.0)
        drawCircleShadow(g, star.center, star.branchWidth / 2.0, 270.0, self.alpha)
        g.restore()
        
    def drawStarBranch(self, g, star, branch):
        g.save()
        branchOutline = branch.outline
        branchBounds = branchOutline.boundingRect()
        # still need to rotate by branch.rotation degrees
        gradient = QLinearGradient(branchBounds.topLeft(), branchBounds.bottomRight())
        gradient.setColorAt(0.0, branch.branchColor)
        gradient.setColorAt(1.0, self.endBranchColor)
        g.setPen(self.borderPen)
        g.setBrush(QBrush(gradient))
        g.drawPath(branchOutline)
        g.restore()

class Star(object):
    angles = [270.0, 342.0, 54.0, 126.0, 198.0]
    def __init__(self):
        self.branches = [StarBranch() for i in range(0, 5)]
        self.center = QPointF()
        self.radius = 0.0
        self.branchSize = 0.0
        self.branchWidth = 0.0
    
    def update(self):
        for i, branch in enumerate(self.branches):
            angle = Star.angles[i]
            branch.origin = transform(self.center, self.radius, getRadians(angle))
            branch.angle = 36.0
            branch.width = self.branchWidth
            branch.size = self.branchSize
            branch.rotation = angle

class StarBranch(object):
    def __init__(self):
        self.origin = QPointF()
        self.width = self.size = 0.0
        self.angle = self.rotation = 0.0
        self.branchColor = QColor()
    
    @property
    def outerCenter(self):
        A, B, C, E, F = self.computePoints()
        return middle(middle(A, E), middle(B, F))
    
    def computePoints(self):
        alpha = getRadians(self.angle)
        height = self.size * math.tan(alpha)
        a = self.size / math.cos(alpha)
        b = self.width / math.sin(Degrees90 - alpha)
        c = self.size * ((b + height) / height)
        r = getRadians(self.rotation)
        E = transform(self.origin, c, Degrees180 + alpha + r)
        F = transform(self.origin, c, Degrees180 - alpha + r)
        B = transform(F, self.width, Degrees270 - alpha + r)
        A = transform(E, self.width, Degrees90 + alpha + r)
        C = transform(self.origin, c - self.size, Degrees180 + r)
        return (A, B, C, E, F)
    
    @property
    def outline(self):
        p = QPainterPath()
        A, B, C, E, F = self.computePoints()
        p.moveTo(self.origin)
        p.lineTo(F)
        C2 = getCircleBounds(middle(B, F), self.width / 2.0)
        p.arcTo(C2, 90.0 - self.angle + self.rotation, -180.0)
        p.lineTo(B)
        p.lineTo(C)
        p.lineTo(A)
        C1 = getCircleBounds(middle(A, E), self.width / 2.0)
        p.arcTo(C1, 90.0 + self.angle + self.rotation, -180.0)
        p.lineTo(E)
        p.lineTo(self.origin)
        p.closeSubpath()
        return p