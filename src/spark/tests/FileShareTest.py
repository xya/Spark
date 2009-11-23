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
from spark.async import Future

class FileShareTest(unittest.TestCase):
    def testAddFile(self):
        """ Files added through addLocalFile should be retrievable with listFiles """
        s = FileShare()
        self.assertEqual(0, len(s.listFiles()))
        id = s.addLocalFile("FileShareTest.py")
        files = s.listFiles()
        self.assertEqual(1, len(files))
        file = files[0]
        self.assertEqual("FileShareTest.py", file.name)
        self.assertEqual(id, file.id)
    
    def testRemoveExistingFile(self):
        """ removeFile should remove the file with the specified ID from the list """
        s = FileShare()
        id = s.addLocalFile("FileShareTest.py")
        s.removeFile(id)
        self.assertEqual(0, len(s.listFiles()))
    
    def testRemoveInvalidFile(self):
        """ removeFile should fail if the given ID doesn't match any file """
        s = FileShare()
        id = s.addLocalFile("FileShareTest.py")
        try:
            s.removeFile("foo")
        except:
            pass
        else:
            self.fail("removeFile should fail if the ID is invalid")
    
    def testAddNotification(self):
        """ Notifications should be sent when a file is added to the list """
        notifications = []
        def fileAdded(file):
            notifications.append(file)
        s = FileShare()
        s.FileAdded += fileAdded
        s.watch()
        s.addLocalFile("FileShareTest.py")
        self.assertEqual(1, len(notifications))

    def testRemoveNotification(self):
        """ Notifications should be sent when a file is removed from the list """
        notifications = []
        def fileRemoved(file):
            notifications.append(file)
        s = FileShare()
        s.FileRemoved += fileRemoved
        id = s.addLocalFile("FileShareTest.py")
        s.watch()
        s.removeFile(id)
        self.assertEqual(1, len(notifications))

if __name__ == '__main__':
    unittest.main()