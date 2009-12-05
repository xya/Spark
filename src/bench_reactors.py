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
import time
import threading
import logging
from spark.async import coroutine, Reactor
from spark.messaging import Block, messageReader, messageWriter

TestDir = "/home/xya/Public/Spark"
TestFile = "I'm a lagger.mp3"

def run_bench():
    sourcePath = os.path.join(TestDir, TestFile)
    destPath = sourcePath + ".1"
    lock = threading.RLock()
    reactor = Reactor.create()
    reactor.launch_thread()
    try:
        p1, p2 = reactor.pipes()
        fSend = sender(sourcePath, reactor, p1, lock)
        fReceive = receiver(destPath, reactor, p2, lock)
        started = time.time()
        sent = fSend.result
        p1.close()
        received = fReceive.result
        duration = time.time() - started
        print "Transfered in %f seconds" % duration
    finally:
        reactor.close()

@coroutine
def sender(sourcePath, reactor, writer, lock):
    blockID = 0
    blockSent = 0
    messenger = messageWriter(writer)
    with reactor.open(sourcePath, 'r') as reader:
        while True:
            data = yield reader.beginRead(1024)
            if len(data) == 0:
                break
            block = Block(0, blockID, data)
            yield messenger.write(block)
            blockID += 1
            blockSent += 1
    yield blockSent

@coroutine
def receiver(destPath, reactor, reader, lock):
    messenger = messageReader(reader)
    blockReceived = 0
    with reactor.open(destPath, 'w') as writer:
        while True:
            block = yield messenger.read()
            if block is None:
                break
            yield writer.beginWrite(block.blockData)
            blockReceived += 1
    yield blockReceived

if __name__ == '__main__':
    logging.basicConfig(level=10)
    run_bench()