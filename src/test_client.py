#!/usr/bin/env python
import os
import traceback
from spark.messaging.messages import Request
from spark.fileshare import FileShareSession

print "PID: %i" % os.getpid()
remoteAddr = ("127.0.0.1", 4550)
s = FileShareSession()
s.connect(remoteAddr).wait(1.0)
print "Connected to %s" % repr(remoteAddr)
try:
    response = s.remoteShare.listFiles({}).wait(1.0)[0]
    print str(response)
except:
    traceback.print_exc()
s.disconnect().wait(1.0)
print "Disconnected"