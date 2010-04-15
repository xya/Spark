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

""" This module is used to communicate with an external process for debugging purporses.
This can come useful in case of deadlock. """

import os
import threading
import sys
import traceback
import pdb
from spark.core import *

def start_watcher():
    if os.path.exists("spark_debug_pipe"):
        t = threading.Thread(target=_entry, name="watcher")
        t.daemon = True
        t.start()

def _entry():
    Process.attach("Debug")
    log = Process.logger()
    with open("spark_debug_pipe", "r") as p:
        for line in p:
            line = line.rstrip()
            log.info("Received %s.", repr(line))
            if line == "dump-threads":
                _dump_threads(log)
            elif line == "pdb":
                _pdb(log)

def _dump_threads(log):
    currentID = threading.current_thread().ident
    for threadID, frame in sys._current_frames().items():
        if currentID != threadID:
            threadName = _thread_name_by_id(threadID)
            stack = traceback.format_stack(frame)
            if stack[-1].endswith("\n"):
                stack[-1] = stack[-1].rstrip()
            log.info("Stack frame for thread %s:\n%s", repr(threadName), "".join(stack))

def _thread_name_by_id(threadID):
    for t in threading.enumerate():
        if t.ident == threadID:
            return t.name
    return threadID

def _pdb(log):
    pdb.set_trace()