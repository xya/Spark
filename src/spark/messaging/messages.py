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
from spark.async import Future, Process, ProcessNotifier

__all__ = ["Message", "TextMessage", "Request", "Response",
           "Notification", "Blob", "Block", "match", "MessageMatcher", "Event"]

def match(pattern, o):
    """ Try to match an object against a pattern. Return True if the pattern is matched. """
    messageAttr = ("type", "tag", "params", "transID")
    if pattern is None:
        return True
    if type(pattern) is type:
        return type(o) is pattern
    elif all(hasattr(pattern, at) for at in messageAttr):
        # match a message
        return all(match(getattr(pattern, at), getattr(o, at, None)) for at in messageAttr)
    elif type(pattern) is str or type(pattern) is unicode:
        return pattern == o
    elif hasattr(pattern, "__len__") and hasattr(o, "__len__"):
        if len(pattern) != len(o):
            return False
        else:
            for i in range(0, len(pattern)):
                if not match(pattern[i], o[i]):
                    return False
            return True
    else:
        return pattern == o

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

class TextMessage(Message):
    REQUEST = ">"
    RESPONSE = "<"
    NOTIFICATION = "!"
    Types = [REQUEST, RESPONSE, NOTIFICATION]
    
    def __init__(self, type, tag, params=None, transID=None):
        self.type = type
        self.tag = tag
        self.transID = transID
        self.params = params
    
    def canonical(self):
        return " ".join([self.type, self.tag, str(self.transID),
            json.dumps(self.params, sort_keys=True, default=_serializable)])

class Request(TextMessage):
    def __init__(self, tag, params=None, transID=None):
        super(Request, self).__init__(TextMessage.REQUEST, tag, params, transID)

class Response(TextMessage):
    def __init__(self, tag, params=None, transID=None):
        super(Response, self).__init__(TextMessage.RESPONSE, tag, params, transID)

class Notification(TextMessage):
    def __init__(self, tag, params=None, transID=None):
        super(Notification, self).__init__(TextMessage.NOTIFICATION, tag, params, transID)

class Blob(Message):
    Type = Struct("BB")
    
    def __init__(self):
        super(Blob, self).__init__()
    
    @property
    def data(self):
        raise NotImplementedError()
    
    def canonical(self):
        data = self.data
        cls = self.__class__
        return "".join([cls.Type.pack(0, cls.ID), data])

class Block(Blob):
    Header = Struct("!HIH")
    ID = 1
    
    def __init__(self, transferID, blockID, blockData):
        super(Block, self).__init__()
        self.transferID = transferID
        self.blockID = blockID
        self.blockData = blockData
    
    @property
    def data(self):
        return Block.Header.pack(self.transferID, self.blockID,
                                 len(self.blockData)) + self.blockData

def _serializable(obj):
    if hasattr(obj, "__getstate__"):
        return obj.__getstate__()
    else:
        return obj.__dict__

class MessageWriter(object):
    def __init__(self, file):
        self.file = file
        
    def format(self, m):
        data = " %s\r\n" % str(m)
        return "%04x%s" % (len(data), data)
    
    def write(self, m):
        """ Write a message to the file. """
        return self.file.write(self.format(m))

class Event(ProcessNotifier):
    """ Notification event which can be suscribed by other processes. """
    def __init__(self, name, lock=None):
        super(Event, self).__init__(lock)
        self.name = name
    
    def suscribe(self, pid=None, matcher=None, callable=None, result=True):
        """ Suscribe a process to start receiving notifications of this event. """
        if matcher:
            matcher.addNotification(self.name, callable, result)
        super(Event, self).suscribe(pid)
    
    def __call__(self, *args):
        """ Send a notification to all suscribed processes. """
        if len(args) == 0:
            params = None
        elif len(args) == 1:
            params = args[0]
        else:
            params = args
        m = Notification(self.name, params)
        super(Event, self).__call__(m)

class MessageMatcher(object):
    """ Matches messages against a list of patterns. """
    def __init__(self):
        self.rules = []
    
    def addPattern(self, pattern, callable=None, result=True):
        """ Add a pattern to match messages. """
        self.rules.append((pattern, callable, result))
    
    def removePattern(self, pattern, callable=None, result=True):
        """ Remove a pattern from the list. """
        self.rules.remove((pattern, callable, result))
    
    def addNotification(self, tag, callable=None, result=True):
        """ Add a pattern to match notifications that have a certain tag. """
        self.addPattern(Notification(tag), callable, result)
    
    def match(self, m, *args):
        """ Match the message against the patterns. """
        for pattern, callable, result in reversed(self.rules):
            if match(pattern, m):
                if callable:
                    callable(m, *args)
                return result
        Process.logger().info("No rule matched message %s" % str(m))
        return False
    
    def run(self, *args):
        """ Retrieve messages from the current process' queue while they match any pattern. """
        while True:
            m = Process.receive()
            if not self.match(m, *args):
                break