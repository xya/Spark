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

import os
from distutils.core import setup
from distutils.command.install import install, INSTALL_SCHEMES
from distutils import file_util, dir_util

class CustomInstall(install):
    def run(self):
        install.run(self)
        # create a symbolink link in /usr/bin to run Spark
        root = os.path.abspath(self.root)
        if not self.install_purelib.startswith(root):
            raise Exception("Couldn't remove prefix from path")
        deploy_purelib = self.install_purelib[len(root):]
        source = os.path.join(deploy_purelib, "spark", "start_gui.py")
        symlink = os.path.join(self.install_scripts, "spark")
        dir_util.mkpath(self.install_scripts)
        if not os.path.islink(symlink):
            os.symlink(source, symlink)
        # make it executable
        actual = os.path.join(self.install_purelib, "spark", "start_gui.py")
        os.chmod(actual, 0o755)

def dir_to_data_files(path):
    """ Enumerate a directory's files and return the list in 'data_files' format. """
    return [(root, [os.path.join(root, file) for file in files])
             for root, dirs, files in os.walk(path) if not dirs and files]

data_dirs = ["icons"]
data_files = []
for dir in data_dirs:
    data_files.extend(dir_to_data_files(dir))

setup(name='Spark',
    version='0.0.2',
    description='Simple file-transfer tool',
    license='GPL',
    author='Pierre-André Saulais',
    author_email='pasaulais@free.fr',
    url='http://pasaulais.free.fr/spark',
    packages=['spark',
              'spark.core',
              'spark.fileshare',
              'spark.gui',
              'spark.messaging',
              'spark.tests'],
    data_files=data_files,
    package_dir = {'': 'src'},
    cmdclass={"install": CustomInstall},
    script_name=__file__)