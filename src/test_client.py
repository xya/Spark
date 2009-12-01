#!/usr/bin/env python
import os
import traceback
import logging
from spark.messaging.messages import Request
from spark.fileshare import FileShareSession

logging.basicConfig(level=logging.DEBUG)
print "PID: %i" % os.getpid()
remoteAddr = ("127.0.0.1", 4550)
s = FileShareSession()
s.connect(remoteAddr).wait(1.0)
try:
    response = s.remoteShare.listFiles({}).wait(1.0)
except:
    traceback.print_exc()
s.disconnect().wait(1.0)
print "Disconnected"