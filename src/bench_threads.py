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
    r, w = os.pipe()
    #fr, fw = os.fdopen(r, 'r'), os.fdopen(w, 'w')
    tSend = threading.Thread(target=sender, args=(sourcePath, w))
    started = time.time()
    tSend.start()
    size = receiver(destPath, r)
    tSend.join()
    duration = time.time() - started
    speed = size / duration
    print "[Threads] Transfered %s in %f seconds (%s/s)" % (formatSize(size),
        duration, formatSize(speed))

Units = [("KiB", 1024), ("MiB", 1024 * 1024), ("GiB", 1024 * 1024 * 1024)]
def formatSize(size):
    for unit, count in reversed(Units):
        if size >= count:
            return "%0.2f %s" % (size / float(count), unit)
    return "%d byte" % size

def sender(sourcePath, writeFD):
    position = 0
    with open(sourcePath, 'r') as reader:
        logging.info("sending from file %i to pipe %i" % (reader.fileno(), writeFD))
        try:
            while True:
                data = reader.read(4096)
                read = len(data)
                #logging.info("Read %i bytes from the file" % read)
                if read == 0:
                    break
                else:
                    position += read
                os.write(writeFD, data)
        except Exception:
            logging.exception("Error while sending the file")
    logging.info("Closing pipe %i" % writeFD)
    os.close(writeFD)

def receiver(destPath, readFD):
    position = 0
    with open(destPath, 'w') as writer:
        logging.info("receiving from pipe %i to file %i" % (readFD, writer.fileno()))
        try:
            while True:
                data = os.read(readFD, 4096)
                if len(data) == 0:
                    break
                writer.write(data)
                position += len(data)
        except Exception:
            logging.exception("Error while receiving the file")
    logging.info("Closing pipe %i" % readFD)
    os.close(readFD)
    return position

profiling = False
if profiling:
    import cProfile
    command = """run_bench()"""
    cProfile.runctx(command, globals(), locals(), filename="run_bench.profile")
else:
    logging.basicConfig(level=logging.DEBUG)
    run_bench()
