# -*- coding: utf-8 -*-
#
# Copyright (C) 2009, 2010 Pierre-André Saulais <pasaulais@free.fr>
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
import re
import signal
import threading
import sys
import traceback

_enabled = False
_thread = None
Process = None

def enabled():
    return _enabled

def start_watcher(pipe_name="watcher"):
    global _thread, _enabled, Process
    if _thread is None:
        from spark.core.process import Process as _Process
        Process = _Process
        _enabled = True
        _thread = threading.Thread(target=_entry, name="watcher", args=(pipe_name, ))
        _thread.daemon = True
        _thread.start()

def launch_remote_debugger(*args):
    import rpdb2
    rpdb2.start_embedded_debugger("watcher")

def _entry(pipe_name):
    Process.attach("Debug")
    try:
        log = Process.logger()
        path = os.path.realpath(pipe_name)
        if not os.path.exists(path):
            os.mkfifo(path)
        log.info("Listening on pipe %s.", repr(path))
        while True:
            with open(path, "r") as p:
                for line in p:
                    line = line.rstrip()
                    log.info("Received %s.", repr(line))
                    try:
                        _handle_command(line, log)
                    except Exception:
                        log.exception("Error while executing command")
    finally:
        Process.detach()

def _handle_command(line, log):
    from spark.core.process import Command
    if line == "dump-threads":
        _dump_threads(log)
    elif line == "pdb":
        import pdb
        pdb.set_trace()
    elif line == "rpdb":
        launch_remote_debugger()
    elif line == "term":
        os.kill(os.getpid(), signal.SIGTERM)
    elif line == "kill":
        os.kill(os.getpid(), signal.SIGKILL)
    elif re.match("^send-process \d+ .+$", line):
        chunks = line.split(" ", 2)
        pid = int(chunks[1])
        Process.send(pid, eval(chunks[2]))
    elif re.match("^debug-process \d+$", line):
        chunks = line.split(" ")
        pid = int(chunks[1])
        Process.send(pid, Command("rpdb"))
    elif re.match("^kill-process \d+$", line):
        chunks = line.split(" ")
        pid = int(chunks[1])
        Process.kill(pid)

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