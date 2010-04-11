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

import unittest
from spark.messaging import *
from spark.async import Future, Event
from spark.tests.common import run_tests, assertMatch, assertNoMatch
from spark.tests.ProtocolTest import testRequest, testResponse, testNotification, testBlock

class MockSender(Messenger, MessageDelivery):
    def __init__(self):
        super(MockSender, self).__init__()
        self.sent = []
    
    def sendMessage(self, message):
        self.sent.append(message)
        return Future.done(message)

class MessageDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.requests = []
        self.notifications = []
        self.responses = []
        self.delivery = MockSender()
        self.onMessageReceived = self.messages.append
        self.onRequestReceived = self.requests.append
        self.onNotificationReceived = self.notifications.append
    
    def assertMessageCount(self, requests, responses, notifications, messages):
        self.assertEqual(requests, len(self.requests))
        self.assertEqual(responses, len(self.responses))
        self.assertEqual(notifications, len(self.notifications))
        self.assertEqual(messages, len(self.messages))
    
    def assertMessagesEqual(self, expected, actual):
        if expected is None:
            self.assertEqual(expected, actual)
        else:
            self.assertEqual(str(expected), str(actual))
    
    def testSendRequest(self):
        """ Sending a request should attribute it an unique transaction ID. """
        req = testRequest()
        req.transID = None
        self.delivery.sendRequest(req)
        self.assertNotEqual(None, req.transID)
        req2 = testRequest()
        req2.transID = None
        self.delivery.sendRequest(req2)
        self.assertNotEqual(None, req2.transID)
        self.assertNotEqual(req.transID, req2.transID)
        
    def testDeliverRequest(self):
        """ Receiving a request should call the recipient's requestReceived method. """
        req = testRequest()
        self.delivery.deliverMessage(req, self)
        self.assertMessageCount(1, 0, 0, 0)
        self.assertMessagesEqual(req, self.requests[0])
    
    def testDeliverNotification(self):
        """ Receiving a notification should call the recipient's notificationReceived method. """
        notif = testNotification()
        self.delivery.deliverMessage(notif, self)
        self.assertMessageCount(0, 0, 1, 0)
        self.assertMessagesEqual(notif, self.notifications[0])
    
    def testDeliverBlock(self):
        """ Receiving a block should call the recipient's messageReceived method. """
        block = testBlock()
        self.delivery.deliverMessage(block, self)
        self.assertMessageCount(0, 0, 0, 1)
        self.assertMessagesEqual(block, self.messages[0])
    
    def testDeliverResponse(self):
        """ Receiving a response matching a previous request should deliver it to the sender. """
        req = testRequest()
        self.delivery.sendRequest(req).after(self.responseReceived)
        self.assertMessageCount(0, 0, 0, 0)
        resp = testResponse()
        resp.transID = req.transID + 1  # response not matching the request
        resp2 = testResponse()
        resp2.transID = req.transID     # response matching the request
        self.delivery.deliverMessage(resp, self)
        self.assertMessageCount(0, 0, 0, 0)
        self.delivery.deliverMessage(resp2, self)
        self.assertMessageCount(0, 1, 0, 0)
        self.assertMessagesEqual(resp2, self.responses[0])
    
    def responseReceived(self, prev):
        self.responses.append(prev.result)

class MessageMatchingTest(unittest.TestCase):
    def testString(self):
        """ match() should properly match string patterns """
        assertMatch("foo", "foo")
        assertNoMatch("foo", "bar")
    
    def testTuples(self):
        """ match() should properly match tuple patterns """
        assertMatch(("foo", int), ("foo", 1))
        assertNoMatch(("foo", int), ("bar", 1))
    
    def testMessages(self):
        """ match() should properly match message patterns """
        assertMatch(Request("swap", str, str), Request("swap", "foo", "bar").withID(1))
        assertMatch(Event("listening", None), Event('listening', ('127.0.0.1', 4550)))
        assertNoMatch(Request("paws"), Request("swap", "foo", "bar").withID(1))
        assertNoMatch(Request("swap", "foo", "bar").withID(1), Request("swap"))
        assertNoMatch(('disconnect', ), Event("protocol-negociated", "SPARKv1"))
    
    def testMatchSubclass(self):
        """ match()  should match a type if it is one of its parent types """
        assertMatch(basestring, u"foo")

if __name__ == '__main__':
    run_tests()