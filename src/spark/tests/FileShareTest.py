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

import unittest
import os
import functools
from spark.async import Future
from spark.fileshare import FileShare
from spark.tests.AioTest import runReactors

class FileShareTest(unittest.TestCase):
    @runReactors
    def testAddFile(self, rea):
        """ Files added through addFile() should be retrievable with files() """
        s = FileShare(rea)
        self.assertEqual(0, len(s.files()))
        id = s.addFile("FileShareTest.py")
        files = s.files()
        self.assertEqual(1, len(files))
        file = files[0]
        self.assertEqual("FileShareTest.py", file.name)
        self.assertEqual(id, file.id)
    
    @runReactors
    def testRemoveExistingFile(self, rea):
        """ removeFile should remove the file with the specified ID from the list """
        s = FileShare(rea)
        id = s.addFile("FileShareTest.py")
        s.removeFile(id)
        self.assertEqual(0, len(s.listFiles()))
    
    @runReactors
    def testRemoveInvalidFile(self, rea):
        """ removeFile should fail if the given ID doesn't match any file """
        s = FileShare(rea)
        id = s.addFile("FileShareTest.py")
        self.assertRaises(Exception, s.removeFile, "foo")
    
    @runReactors
    def testAddNotification(self, rea):
        """ Notifications should be sent when a file is added to the list """
        notifications = []
        def fileAdded(file):
            notifications.append(file)
        s = FileShare(rea)
        s.fileAdded += fileAdded
        s.addFile("FileShareTest.py")
        self.assertEqual(1, len(notifications))

    @runReactors
    def testRemoveNotification(self, rea):
        """ Notifications should be sent when a file is removed from the list """
        notifications = []
        def fileRemoved(file):
            notifications.append(file)
        s = FileShare(rea)
        s.fileRemoved += fileRemoved
        id = s.addFile("FileShareTest.py")
        s.removeFile(id)
        self.assertEqual(1, len(notifications))

if __name__ == '__main__':
    import sys
    unittest.main(argv=sys.argv)