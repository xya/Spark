#!/usr/bin/env python
import os
from spark.async import Future
from spark.fileshare.session import FileShareSession

print "PID: %i" % os.getpid()
s = FileShareSession()
remoteAddr = s.listen(("", 4550), None)[0]
print "Connected to %s" % repr(remoteAddr)
s.join(None)
print "Disconnected"