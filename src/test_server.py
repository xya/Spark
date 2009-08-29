#!/usr/bin/env python
import os
import time
import socket
from spark.async import Future
from spark.session import Session

print "PID: %i" % os.getpid()
s = Session()
remoteAddr = s.listen(("", 4550), None)[0]
print "Connected to %s" % repr(remoteAddr)
s.join(None)
print "Disconnected"