#!/usr/bin/env python
import os
from spark.async import Future
from spark.messaging.messages import Request
from spark.fileshare import FileShareSession

print "PID: %i" % os.getpid()
remoteAddr = ("127.0.0.1", 4550)
s = FileShareSession()
s.connect(remoteAddr, None)
print "Connected to %s" % repr(remoteAddr)
response = s.remoteShare.listFiles({}, None)
print str(response[0])
s.disconnect(None)
print "Disconnected"