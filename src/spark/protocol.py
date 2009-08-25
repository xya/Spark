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

__all__ = ["parser", "writer"]

def parser(file, buffer=4096):
    return SparkProtocolReader(file, buffer)

def writer(file):
    return SparkProtocolWriter(file)

class Message(object):
    def __str__(self):
        text = self.canonical()
        return isinstance(text, unicode) and text.encode('utf-8') or text
    
    def __unicode__(self):
        text = self.canonical()
        return isinstance(text, str) and text.decode('utf-8') or text
    
    def canonical(self):
        ''' Returns the canonical text representation of the message.
        The return value can be a str or unicode object. '''
        raise NotImplementedError()

class SupportedProtocolNames(Message):
    def __init__(self, names):
        self.names = names
    
    def canonical(self):
        return "supports %s" % " ".join(self.names)

class ProtocolName(Message):
    def __init__(self, name):
        self.name = name
    
    def canonical(self):
        return "protocol %s" % self.name

class TextMessage(Message):
    REQUEST = ">"
    RESPONSE = "<"
    NOTIFICATION = "!"
    Types = [REQUEST, RESPONSE, NOTIFICATION]
    
    def __init__(self, type, tag, transID, data=None):
        self.type = type
        self.tag = tag
        self.transID = transID
        self.data = data
    
    def canonical(self):
        chunks = [self.type, " ", self.tag, " ", str(self.transID), " "]
        if not self.data is None:
            chunks.append(json.dumps(self.data))
        return "".join(chunks)

class Blob(Message):
    def __init__(self, data):
        if not isinstance(data, basestring):
            raise TypeError("data must be a string")
        self.data = data
        self.size = len(data)
    
    def canonical(self):
        return "".join(["0x", hex(self.size)[2:].zfill(8), self.data])

class SparkProtocolWriter(object):
    def __init__(self, file):
        self.file = file
    
    def write(self, m):
        self.file.write(str(m))
        self.file.write("\r\n")

class SparkProtocolReader(object):
    def __init__(self, file, buffer):
        self.parser = TextParser(file, buffer, lineinfo=True)
    
    def readAll(self):
        """ Return a sequence containing every message in the file """
        while not self.parser.eof():
            yield self.read()
    
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
        try:
            return int(self.parser.read(length=8), 16)
        except Exception, e:
            self.parser.error(str(e))
    
    def parseSupportedProtocolNames(self):
        names = []
        self.parser.read("supports")
        self.readDelimiter()
        names.append(self.readTag())
        while self.parser.match(self._whitespace, 1):
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
        transID = int(self.parser.parse(self._digit, error='Transaction ID expected'))
        data = None
        if self.parser.fill(1) and self.parser.match(self._whitespace, 1):
            self.readDelimiter()
            jsonData = self.parser.readUntilNewline()
            if len(jsonData) == 0:
                self.parser.error('JSON object expected')
            else:
                data = json.loads(jsonData)
        return TextMessage(type, tag, transID, data)
    
    def parseBlob(self):
        size = self.readSize()
        data = self.parser.read(length=size)
        return Blob(data)

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
    
    def match(self, pred, length=None):
        ''' match(predicate, [length]) -> bool
        Determines whether lookup matches the string predicate. '''
        length = length or len(pred)
        if self.size < length:
            return False
        else:
            text = self.buffer[:length]
        if isinstance(pred, basestring):
            return text == pred
        elif callable(pred):
            return bool(pred(text))
        elif hasattr(pred, 'match'):
            return bool(pred.match(text)) # e.g compiled regexp
        else:
            raise TypeError('Invalid character predicate')

    def read(self, pred=None, length=None, error=None):
        ''' Reads a fixed length string matching the string predicate. '''
        length = length or len(pred)
        self.fill(length)
        if pred and not self.match(pred, length):
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
    
    def _notNewLineChar(self, c, pos=0):
        return c not in ('\n', '\r')
    
    def readUntilNewline(self):
        ''' Reads until a newline character is found. '''
        if self.fill(1) and self._notNewLineChar(self.buffer[0], 0):
            return self.parse(self._notNewLineChar)
        else:
            return ''
        
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
            return self.message