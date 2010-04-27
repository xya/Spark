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

from collections import Sequence
import json
from struct import Struct

__all__ = ["Message", "TextMessage", "Request", "Response", "Notification", "Blob", "Block", "formatMessage"]

class Message(object):
    def to_bytes(self):
        """ Returns the canonical representation of the message, as bytes. """
        raise NotImplementedError()

class TextMessage(Message, Sequence):
    REQUEST = ">"
    RESPONSE = "<"
    NOTIFICATION = "!"
    
    def __init__(self, type, tag, transID, *params):
        self.type = type
        self.tag = tag
        self.transID = transID
        self.params = params
    
    def to_bytes(self):
        return u" ".join([self.type, self.tag, str(self.transID),
            json.dumps(self.params, sort_keys=True, default=_serializable)]).encode("utf8")
    
    def withID(self, transID):
        """ Set the message's transaction ID. """
        self.transID = transID
        return self
    
    def __len__(self):
        return 3 + len(self.params)
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self)[index]
        elif index == 0:
            return self.__class__.__name__
        elif index == 1:
            return self.tag
        elif index == 2:
            return self.transID
        elif (index >= 3) and (index < (len(self.params) + 3)):
            return self.params[index - 3]
        else:
            raise IndexError("Index '%i' out of range" % index)
    
    def __repr__(self):
        return repr(self[:])
    
class Request(TextMessage):
    def __init__(self, tag, *params):
        super(Request, self).__init__(TextMessage.REQUEST, tag, None, *params)

class Response(TextMessage):
    def __init__(self, tag, *params):
        super(Response, self).__init__(TextMessage.RESPONSE, tag, None, *params)

class Notification(TextMessage):
    def __init__(self, tag, *params):
        super(Notification, self).__init__(TextMessage.NOTIFICATION, tag, None, *params)

class Blob(Message, Sequence):
    Type = Struct("BB")
    
    def __init__(self):
        super(Blob, self).__init__()
    
    @property
    def params(self):
        raise NotImplementedError()
    
    @property
    def data(self):
        raise NotImplementedError()
    
    def to_bytes(self):
        data = self.data
        cls = self.__class__
        return bytes().join([cls.Type.pack(0, cls.ID), data])
    
    def __len__(self):
        return 1 + len(self.params)
    
    def __getitem__(self, index):
        cls = self.__class__
        if isinstance(index, slice):
            return tuple(self)[index]
        elif index == 0:
            return cls.__name__
        else:
            params = self.params
            if index < (len(params) + 1):
                return params[index - 1]
            else:
                raise IndexError("Index '%i' out of range" % index)
    
    def __repr__(self):
        return repr(self[:])

class Block(Blob):
    Header = Struct("!HIH")
    ID = 1
    
    def __init__(self, transferID=None, blockID=None, blockData=None):
        super(Block, self).__init__()
        self.transferID = transferID
        self.blockID = blockID
        self.blockData = blockData
    
    @property
    def params(self):
        return (self.transferID, self.blockID, self.blockData)
    
    @property
    def data(self):
        return Block.Header.pack(self.transferID, self.blockID,
                                 len(self.blockData)) + self.blockData

def _serializable(obj):
    if hasattr(obj, "__getstate__"):
        return obj.__getstate__()
    elif type(obj) is type:
        return obj.__name__
    else:
        return obj.__dict__

def formatMessage(o, encoding=u"utf8"):
    """ Format an object to be sent as a message. """
    if isinstance(o, bytes):
        data = o
    elif isinstance(o, unicode):
        data = o.encode(encoding)
    elif hasattr(o, u"to_bytes"):
        data = o.to_bytes()
    else:
        raise TypeError("The object should be convertible to bytes.")
    payload = u" ".encode("utf8") + data + u"\n".encode("utf8")
    prefix = u"%04x" % len(payload)
    return prefix.encode(encoding) + payload

class MessageWriter(object):
    def __init__(self, file):
        self.file = file
    
    def write(self, m):
        """ Write a message to the file. """
        return self.file.write(formatMessage(m))