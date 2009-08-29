#!/usr/bin/env python
import time
import socket
from spark.async import Future
from spark.messaging.messages import *
from spark.messaging.protocol import *
from spark.session import SocketFile

conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
conn.connect(("127.0.0.1", 4550))
f = SocketFile(conn)
negociateProtocol(f, True)
reader = messageReader(f)
writer = messageWriter(f)
writer.write(Request("list-files", {"register": True}, 0))
time.sleep(5)
writer.write(Notification("file-added", {"id": "<guid>", "name": "SeisRoX-2.0.9660.exe", "size": 3145728, "last-modified": "20090619T173529.000Z"}, 55))
conn.close()