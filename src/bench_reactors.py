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

import os
import sys
import time
import threading
import logging
import pdb
import stackless
from spark.async import Reactor

if sys.platform.startswith("win32"):
    TestDir = os.path.join(os.path.expanduser("~"), "Mes documents\\Spark")
else:
    TestDir = os.path.join(os.path.expanduser("~"), "Public/Spark")
#TestFile = "dia.clp"
#TestFile = "_iocp.pyd"
TestFile = "I'm a lagger.mp3"

def run_bench():
    sourcePath = os.path.join(TestDir, TestFile)
    destPath = sourcePath + ".1"
    reactors = Reactor.available()
    #reactors.pop(1)
    for reactorType in reactors:
        with reactorType() as reactor:
            run_reactor(sourcePath, destPath, reactor)

def run_reactor(sourcePath, destPath, reactor):
    r, w = reactor.pipe()
    stackless.tasklet(sender)(sourcePath, reactor, w)
    stackless.tasklet(receiver)(destPath, reactor, r)
    started = time.time()
    reactor.run()
    duration = time.time() - started
    size = os.path.getsize(sourcePath)
    speed = size / duration
    print "[%s] Transfered %s in %f seconds (%s/s)" % (reactor.__class__.__name__,
        formatSize(size), duration, formatSize(speed))

Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
def formatSize(size):
    for unit, count in reversed(Units):
        if size >= count:
            return "%0.2f %s" % (size / float(count), unit)
    return "%d byte" % size

def sender(sourcePath, reactor, writer):
    position = 0
    with reactor.open(sourcePath, 'r') as reader:
        logging.info("sending from file %i to pipe %i" % (reader.fileno(), writer.fileno()))
        try:
            while True:
                data = reader.read(4096, position)
                read = len(data)
                #logging.info("Read %i bytes from the file" % read)
                if read == 0:
                    break
                else:
                    position += read
                writer.write(data, position)
        except Exception:
            logging.exception("Error while sending the file")
    logging.info("Closing pipe %i" % writer.fileno())
    writer.close()
    return position

def receiver(destPath, reactor, reader):
    position = 0
    with reactor.open(destPath, 'w') as writer:
        logging.info("receiving from pipe %i to file %i" % (reader.fileno(), writer.fileno()))
        try:
            while True:
                data = reader.read(4096, position)
                if len(data) == 0:
                    break
                writer.write(data, position)
                position += len(data)
        except Exception:
            logging.exception("Error while receiving the file")
    logging.info("Closing pipe %i" % reader.fileno())
    reader.close()
    reactor.close()

profiling = False
if profiling:
    import cProfile
    command = """run_bench()"""
    cProfile.runctx(command, globals(), locals(), filename="run_bench.profile")
else:
    logging.basicConfig(level=logging.DEBUG)
    run_bench()
