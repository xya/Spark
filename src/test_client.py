#!/usr/bin/env python
import os
import traceback
from spark.messaging.messages import Request
from spark.fileshare import FileShareSession

print "PID: %i" % os.getpid()
remoteAddr = ("127.0.0.1", 4550)
s = FileShareSession()
s.connect(remoteAddr).wait()
print "Connected to %s" % repr(remoteAddr)
try:
    response = s.remoteShare.listFiles({}).result
    print str(response)
except:
    traceback.print_exc()
s.disconnect().wait()
print "Disconnected"