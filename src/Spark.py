#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Pierre-André Saulais <pasaulais@free.fr>
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

if __name__ == "__main__":
    import sys
    import os
    import logging
    from PyQt4.QtGui import QApplication
    from spark.gui.main import MainWindow, GuiProcess
    from spark.fileshare import SparkApplication
    from spark.async import process
    if (len(sys.argv) > 1) and (sys.argv[1].find(":") >= 0):
        chunks = sys.argv[1].split(":")
        bindAddr = (chunks[0], int(chunks[1]))
    else:
        bindAddr = None
    qtapp = QApplication(sys.argv)
    logging.basicConfig(level=logging.DEBUG)
    with GuiProcess() as pid:
        with SparkApplication() as appA:
            viewA = MainWindow(appA, pid)
            if bindAddr:
                viewA.setWindowTitle("Spark %s:%i" % bindAddr)
                appA.bind(bindAddr)
            else:
                viewA.setWindowTitle("Spark")
            viewA.show()
            qtapp.exec_()