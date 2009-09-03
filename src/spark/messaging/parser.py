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

import json
from struct import Struct
from spark.async import Future
from spark.messaging.messages import *

__all__ = ["MessageReader"]

class MessageReader(object):
    def __init__(self, file):
        """ Create a new message reader. 'file' must have a 'beginRead' method. """
        self.file = file
        self.jsonDecoder = json.JSONDecoder()
        self.textTypes = {
            TextMessage.REQUEST : Request,
            TextMessage.RESPONSE : Response,
            TextMessage.NOTIFICATION : Notification
        }
        self.blobParsers = {
            Block.ID : self.parseBlock
        }
    
    def read(self):
        """ Asynchronously read a message from the file. """
        cont = Future()
        self.file.beginRead(4).fork(self.messageSizeRead, cont, cont)
        return cont
    
    def messageSizeRead(self, read, cont):
        if len(read) == 0:
            cont.completed(None)
            return
        try:
            size = int(read, 16)
        except:
            cont.failed()
        else:
            self.file.beginRead(size).fork(self.messageDataRead, cont, cont)
    
    def messageDataRead(self, read, cont):
        if len(read) > 0:
            cont.run(self.parse, read.lstrip())
        else:
            cont.error(EOFError())
    
    def parse(self, data):
        if data[0] == '\x00':
            return self.parseBlob(data)
        else:
            return self.parseTextMessage(data.rstrip())
    
    def parseTextMessage(self, data):
        elems = data.split(" ", 3)
        if len(elems) != 4:
            raise ValueError("Invalid number of elements (expected 4, got %i)" % len(elems))
        else:
            type, tag, transID, params = elems
        if not self.textTypes.has_key(type):
            raise ValueError("Unknown type '%s'" % type)
        jsonParams, endIndex = self.jsonDecoder.raw_decode(params)
        intTransID = int(transID)
        return self.textTypes[type](tag, jsonParams, intTransID)
    
    def parseBlob(self, data):
        typeID = ord(data[1])
        try:
            parseFun = self.blobParsers[typeID]
        except KeyError:
            raise ValueError("Unknown blob type '%i'" % typeID)
        else:
            return parseFun(data)
    
    def parseBlock(self, data):
        begin = 2 + Block.Header.size
        transferID, blockID, blockSize = Block.Header.unpack(data[2:begin])
        blockData = data[begin:begin+blockSize]
        if len(blockData) < blockSize:
            raise ValueError("Block data was truncated (expected %i bytes, got %i)"
                    % (blockSize, len(blockData)))
        return Block(transferID, blockID, blockData)