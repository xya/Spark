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

from distutils.core import setup

setup (
    name='Spark',
    version='0.0.1',
    description='Simple file-transfer tool',
    license='GPL',
    author='Pierre-André Saulais',
    author_email='pasaulais@free.fr',
    url='http://pasaulais.free.fr/spark',
    packages=['spark',
              'spark.async',
              'spark.fileshare',
              'spark.gui',
              'spark.messaging',
              'spark.tests'],
    package_dir = {'': 'src'},
    scripts=['src/Spark.py'],
)