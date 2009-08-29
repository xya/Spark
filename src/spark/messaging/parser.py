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
from messages import *

__all__ = ["MessageReader"]

class MessageReader(object):
    def __init__(self, file, buffer):
        self.parser = TextParser(file, buffer, lineinfo=True)
        self.blobParsers = { Block.ID : self.parseBlock }
    
    def readAll(self):
        """ Return a sequence containing every message in the file """
        m = self.read()
        while not m is None:
            yield m
            m = self.read()
    
    def read(self):
        if self.moveNext():
            if self.parser.match('0'):
                return self.parseBlob()
            elif self.parser.match('s'):
                return self.parseSupportedProtocolNames()
            elif self.parser.match('p'):
                return self.parseProtocolName()
            else:
                return self.parseTextMessage()
        else:
            return None
    
    def moveNext(self):
        if self.parser.bof():
            return self.parser.fill(1)
        elif self.parser.eof():
            return False
        else:
            self.parser.readNewline()
            return not self.parser.eof()

    def _whitespace(self, c, pos=0):
        return c == ' '
    
    def _digit(self, c, pos=0):
        return c.isdigit()
    
    def _type(self, c, pos=0):
        return c in TextMessage.Types
    
    def _tag(self, c, pos):
        return not c.isspace()
    
    def readDelimiter(self):
        return self.parser.parse(self._whitespace, error='Delimiter expected')
    
    def readTag(self):
        return self.parser.parse(self._tag, error='Tag expected')
    
    def readSize(self):
        data = self.parser.read(2 + Blob.HEX_DIGITS)
        try:
            return int(data, 16)
        except Exception, e:
            self.parser.error(str(e))
    
    def readInteger(self):
        return int(self.parser.parse(self._digit, error='Number expected'))
    
    def readString(self):
        length = self.readInteger()
        if length == 0:
            return ''
        else:
            self.parser.read(1, self._whitespace, 'Whitespace expected')
            if not self.parser.fill(length):
                self.parser.error('Expected string of length %i' % length)
            return self.parser.remove(length)
    
    def readStruct(self, format):
        data = self.parser.read(format.size)
        try:
            return format.unpack(data)
        except Exception, e:
            self.parser.error(str(e))
    
    def parseSupportedProtocolNames(self):
        names = []
        self.parser.read("supports")
        self.readDelimiter()
        names.append(self.readTag())
        while self.parser.match(1, self._whitespace):
            self.readDelimiter()
            names.append(self.readTag())
        return SupportedProtocolNames(names)
    
    def parseProtocolName(self):
        self.parser.read("protocol")
        self.readDelimiter()
        name = self.readTag()
        return ProtocolName(name)
    
    def parseTextMessage(self):
        type = self.parser.parse(self._type, error='Type expected')
        self.readDelimiter()
        tag = self.readTag()
        self.readDelimiter()
        transID = self.readInteger()
        self.readDelimiter()
        jsonData = self.readString()
        data = jsonData and json.loads(jsonData) or None
        return TextMessage(type, tag, data, transID)
    
    def parseBlob(self):
        size = self.readSize()
        typeID = self.readStruct(Blob.Type)[0]
        try:
            parseFun = self.blobParsers[typeID]
            return parseFun(size - Blob.Type.size)
        except KeyError:
            self.parser.error("Unknown blob type '%i'" % typeID)
    
    def parseBlock(self, size):
        transferID, blockID = self.readStruct(Block.Header)
        blockData = self.parser.read(size - Block.Header.size)
        return Block(transferID, blockID, blockData)

class TextParser(object):
    """ Helper class for implementing a recursive descent text parser
    with a lookahead buffer. """
    def __init__(self, file, lookahead=1, linesep=None, lineinfo=False):
        self.file = file
        self.lookahead = lookahead
        self.linesep = linesep
        self.buffer = ''
        self.size = 0        
        self.pos = 0
        self.lineinfo = lineinfo
        self.line = 1
        self.col = 1
        self.linestate = 0

    def bof(self):
        ''' At beginning of file? '''
        return (self.size == 0) and (self.pos == 0)
    
    def eof(self):
        ''' At end of file? '''
        return (self.size == 0) and (self.pos > 0)
    
    def error(self, message=None):
        ''' Raises a parsing error at the current file location. '''
        message = message or 'Unknown parsing error'
        if self.lineinfo:
            raise TextParsingError(message, self.pos, self.line, self.col)
        else:
            raise TextParsingError(message, self.pos)
    
    def remove(self, count=1):
        ''' Removes count chars from the buffer and returns them,
        or returns an empty string if not enough chars are in the buffer. '''
        if self.size >= count:
            self.buffer, chars = self.buffer[count:], self.buffer[:count]
            self.size -= count
            self.pos += count
            if self.lineinfo:
                self.updateLineState(chars)
            if self.size == 0:
                self.fill(1)
            return chars
        else:
            return ''
    
    def fill(self, count=1):
        ''' Tries to fill the buffer with count chars.
        Returns True if enough chars are in the buffer. '''
        diff = count - self.size
        if diff > 0:
            chars = self.file.read(max(diff, self.lookahead))
            read = len(chars)
            self.buffer += chars
            self.size += read
            return (read - diff) >= 0
        else:
            return True
    
    def updateLineState(self, text):
        ''' Updates the parser's line position state (line, col)
        with the string that was read. '''
        # self.linestate ->
        # 0: last char was 'any' char
        # n: last char was nth char of linesep
        if self.linesep:
            sep = self.linesep
            seplen = len(sep)
            i = self.linestate
            line, col = self.line, self.col
            for char in text:
                if (i < seplen) and (sep[i] == char):                
                    i += 1
                    if i == seplen:
                        i = 0
                        line += 1
                        col = 0
                col += 1
            self.linestate = i
            self.line = line
            self.col = col
        else:
            self.col += len(text)
    
    def match(self, s, pred=None):
        ''' Determines whether lookup matches the string s, or a predicate of length s. '''
        if isinstance(s, basestring):
            length, pred = len(s), s
        else:
            length = s
        if self.size < length:
            return False
        else:
            text = self.buffer[:length]
        if isinstance(pred, basestring):
            return text == pred
        elif hasattr(pred, '__call__'):
            return bool(pred(text))
        elif hasattr(pred, 'match'):
            return bool(pred.match(text)) # e.g compiled regexp
        else:
            raise TypeError('Invalid character predicate')

    def read(self, s, pred=None, error=None):
        ''' Reads the string s, or a predicate of length s. '''
        if isinstance(s, basestring):
            length, pred = len(s), s
        else:
            length = s
        if not self.fill(length) or (pred and not self.match(length, pred)):
            self.error(error)
        return self.remove(length)
    
    def parse(self, pred, error=None):
        ''' Reads a variable length string matching the string predicate. '''        
        if self.fill(1) and pred(self.buffer[0], 0):
            n = 1
            while self.fill(n + 1) and pred(self.buffer[n], n):
                n += 1
            return self.remove(n)
        else:
            self.error(error)

    def readNewline(self):
        ''' Reads a newline. '''
        if self.linesep is None:
            # detect line ending type (UNIX, Windows or legacy MacOS)
            self.fill(2)
            if self.match('\n'):
                self.linesep = '\n'
                self.readNewline()
            elif self.match('\r\n'):
                self.linesep = '\r\n'
                self.readNewline()
            elif self.match('\r'):
                self.linesep = '\r'
                self.readNewline()
            else:
                self.error('Expected newline')
        else:
            return self.read(self.linesep, error='Expected newline')
        
class TextParsingError(Exception):
    ''' Exception raised when parsing a text log file fails. '''
    def __init__(self, msg, pos=-1, line=0, col=0):
        self.msg = msg
        self.pos = pos
        self.line = line
        self.col = col
    
    def __str__(self):
        if self.pos >= 0 and self.line > 0 and self.col > 0:
            return "%s (at char %i, line %i:%i)" % (self.msg,
                self.pos, self.line, self.col)
        elif self.pos >= 0:
            return "%s (at char %i)" % (self.msg, self.pos)
        else:
            return self.msg