# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Pierre-André Saulais <pasaulais@free.fr>
#
# This file is part of the Spark File-transfer Tool.
#
# Spark is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Spark is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Spark; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from Crypto.Util.randpool import RandomPool_DeprecationWarning
import warnings
warnings.filters.append(('ignore', None, RandomPool_DeprecationWarning, None, 0))
import paramiko
import socket
import binascii
import time
import sys

HOST = "127.0.0.1"
PORT = 4551

def key_get_fingerprint(key):
    h = binascii.hexlify(key.get_fingerprint())
    return ':'.join([h[i*2:(i*2)+2] for i in range(0, 16)])

def run_client():
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    conn.connect((HOST, PORT))
    print "Connected to %s" % repr((HOST, PORT))
    t = paramiko.Transport(conn)
    t.start_client()
    server_key = t.get_remote_server_key()
    print "Remote host has public key '%s'" % key_get_fingerprint(server_key)
    
    a = paramiko.Agent()
    keys = a.get_keys()
    if len(keys) > 0:
        pk = keys[0]
        print "Using key '%s' from agent" % key_get_fingerprint(pk)
    else:
        pk = paramiko.RSAKey(filename="test-client-key")
        print "Loaded peer key '%s'" % key_get_fingerprint(pk)
    t.auth_publickey("xya", pk)
    chan = t.open_session()
    print "Channel opened, reading from stdin and sending to server:"
    for line in sys.stdin:
        chan.send(line)
    chan.close()
    t.close()
    
def run_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(1)
    print "Waiting for incoming connection on %s" % repr((HOST, PORT))
    conn, remoteAddr = s.accept()
    try:
        server_connected(conn, remoteAddr)
    finally:
        conn.close()

def server_connected(conn, remoteAddr):
    print "Connected to %s" % repr(remoteAddr)
    a = paramiko.Agent()
    keys = a.get_keys()
    if len(keys) > 0:
        pk = keys[0]
        print "Using key '%s' from agent" % key_get_fingerprint(pk)
    else:
        pk = paramiko.RSAKey(filename="test-server-key")
        print "Loaded host key '%s'" % key_get_fingerprint(pk)
    t = paramiko.Transport(conn)
    t.add_server_key(pk)
    t.start_server(server=SSHPipeServer())
    chan = t.accept()
    print "Channel opened, client data follows:"
    for line in chan.makefile():
        print line,
    t.close()

class SSHPipeServer(paramiko.ServerInterface):
    def check_auth_publickey(self, username, key):
        print "Remote peer offering public key '%s'" % key_get_fingerprint(key)
        return paramiko.AUTH_SUCCESSFUL
    
    def get_allowed_auths(self, username):
        return "publickey"
    
    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        else:
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "server":
        run_server()
    elif len(sys.argv) == 2 and sys.argv[1] == "client":
        run_client()
    else:
        print "Usage: %s client|server" % sys.argv[0]
