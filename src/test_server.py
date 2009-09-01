#!/usr/bin/env python
import os
import signal
from spark.fileshare.session import FileShareSession

print "PID: %i" % os.getpid()
s = FileShareSession()
remoteAddr = s.listen(("", 4550)).result
print "Connected to %s" % repr(remoteAddr)
s.join().wait(1.0)
print "Disconnected"