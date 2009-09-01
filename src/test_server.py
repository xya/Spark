#!/usr/bin/env python
import os
from spark.fileshare.session import FileShareSession

print "PID: %i" % os.getpid()
s = FileShareSession()
remoteAddr = s.listen(("", 4550)).result
print "Connected to %s" % repr(remoteAddr)
s.join().wait()
print "Disconnected"