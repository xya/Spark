#!/usr/bin/python
import sys
import os
import socket

from gnutls.crypto import *
from gnutls.connection import *

#from gnutls.library.types import gnutls_log_func
#from gnutls.library.functions import gnutls_global_set_log_function, gnutls_global_set_log_level
#
#def log_func(level, message):
#    print level, message,
#
#log_func_ptr = gnutls_log_func(log_func)
#gnutls_global_set_log_function(log_func_ptr)
#gnutls_global_set_log_level(5)

keyring = OpenPGPKeyring(open('pubring.gpg').read())
cert = OpenPGPCertificate(open('alice.pub.gpg').read())
key = OpenPGPPrivateKey(open('alice.priv.gpg').read())
cred = OpenPGPCredentials(cert, key)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
session = ClientSession(sock, cred)
session.connect(('localhost', 10000))

try:
    session.handshake()
    peer_cert = session.peer_certificate
    try:
        peer_name = "%s (created %s) " % (peer_cert.name, peer_cert.creation_time)
    except AttributeError:
        peer_name = 'Unknown'
    print 'Connected to:', peer_name
    print 'Protocol:     ', session.protocol
    print 'KX algorithm: ', session.kx_algorithm
    print 'Cipher:       ', session.cipher
    print 'MAC algorithm:', session.mac_algorithm
    print 'Compression:  ', session.compression
    peer_cert.verify(keyring)
except Exception, e:
    print 'Handshake failed:', e
    session.bye()
else:
    session.send("test\r\n")
    buf = session.recv(1024)
    if len(buf):
        print 'Received: ', buf.rstrip()
    session.bye()
session.shutdown()
session.close()