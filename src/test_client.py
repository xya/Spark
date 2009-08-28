#!/usr/bin/env python
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
writer.write(TextMessage(TextMessage.REQUEST, "list-files", {"register": True}, 0))
conn.shutdown(socket.SHUT_RDWR)
conn.close()