#!/usr/bin/env python
from __future__ import print_function
import os
import signal
import logging
from spark.fileshare.session import FileShareSession

logging.basicConfig(level=logging.DEBUG)
print("PID: %i" % os.getpid())
s = FileShareSession()
remoteAddr = s.listen(("", 4550)).result
s.join().wait(1.0)
print("Disconnected")