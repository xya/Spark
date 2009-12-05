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

TestDir = "C:\Documents and Settings\Xya\Mes documents\Spark"
#TestFile = "_iocp.pyd"
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
    position = 0
    messenger = messageWriter(writer)
    with reactor.open(sourcePath, 'r') as reader:
        try:
            while True:
                data = yield reader.beginRead(4096, position)
                read = len(data)
                if read == 0:
                    break
                else:
                    position += read
                block = Block(0, blockID, data)
                yield messenger.write(block)
                blockID += 1
        except Exception:
            logging.exception("Error while sending file")
    writer.close()
    yield blockSent

@coroutine
def receiver(destPath, reactor, reader):
    messenger = messageReader(reader)
    position = 0
    with reactor.open(destPath, 'w') as writer:
        try:
            while True:
                block = yield messenger.read()
                if block is None:
                    break
                yield writer.beginWrite(block.blockData, position)
                position += len(block.blockData)
        except Exception:
            logging.exception("Error while sending file")
    reader.close()
    reactor.close()
    yield blockReceived

run_bench()