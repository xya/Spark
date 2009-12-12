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
from spark.async import coroutine, Reactor
from spark.messaging import Block, messageReader, messageWriter

TestDir = "/home/xya/Public/Spark"
#TestFile = "dia.clp"
TestFile = "I'm a lagger.mp3"

def run_bench():
    sourcePath = os.path.join(TestDir, TestFile)
    destPath = sourcePath + ".1"
    reactor = Reactor.create()
    r, w = reactor.pipe()
    fSend = sender(sourcePath, reactor, w)
    fReceive = receiver(destPath, reactor, r)
    started = time.time()
    reactor.run()
    duration = time.time() - started
    print "Transfered in %f seconds" % duration

@coroutine
def sender(sourcePath, reactor, writer):
    blockID = 0
    blockSent = 0
    messenger = messageWriter(writer)
    with reactor.open(sourcePath, 'r') as reader:
        logging.info("sending from file %i to pipe %i" % (reader.fileno, writer.fileno))
        try:
            while True:
                data = yield reader.beginRead(4096)
                if len(data) == 0:
                    break
                block = Block(0, blockID, data)
                yield messenger.write(block)
                blockID += 1
                blockSent += 1
        except Exception:
            logging.exception("Error while sending the file")
    logging.info("Closing pipe %i" % writer.fileno)
    writer.close()
    yield blockSent

@coroutine
def receiver(destPath, reactor, reader):
    messenger = messageReader(reader)
    blockReceived = 0
    with reactor.open(destPath, 'w') as writer:
        logging.info("receiving from pipe %i to file %i" % (reader.fileno, writer.fileno))
        try:
            while True:
                block = yield messenger.read()
                if block is None:
                    break
                yield writer.beginWrite(block.blockData)
                blockReceived += 1
        except Exception:
            logging.exception("Error while receiving the file")
    logging.info("Closing pipe %i" % reader.fileno)
    reader.close()
    reactor.close()
    yield blockReceived

import hotshot
import hotshot.stats
import timeit

if len(sys.argv) != 2:
    print 'usage: python bench_reactors.py (hotshot|timeit)'    
else:
    if sys.argv[1] == 'hotshot':
        prof = hotshot.Profile('reactor_bench')
        prof.runcall(run_bench)
        prof.close()
        s = hotshot.stats.load('reactor_bench')
        s.strip_dirs()
        s.sort_stats('time').print_stats(20)
        s.sort_stats('cum').print_stats(20)
        s.sort_stats('call').print_stats(20)
        
    elif sys.argv[1] == 'timeit':
        t = timeit.Timer('run_bench()', 'from __main__ import run_bench')
        times = t.repeat(3, 1)
        print min(times), times
    else:
        logging.basicConfig(level=10)
        run_bench()