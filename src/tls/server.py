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
cert = OpenPGPCertificate(open('barney.pub.gpg').read())
key = OpenPGPPrivateKey(open('barney.priv.gpg').read())
cred = OpenPGPCredentials(cert, key)
cred.attach_dh_params()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', 10000))
sock.listen(0)

conn, address = sock.accept()
session = ServerSession(conn, cred, True)
try:
    session.handshake()
    peer_cert = session.peer_certificate
    try:
        peer_name = "%s (created %s) " % (peer_cert.name, peer_cert.creation_time)
    except AttributeError:
        peer_name = 'Unknown'
    print 'New connection from:', peer_name
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
    while True:
        try:
            buf = session.recv(1024)
            if buf == 0 or buf == '':
                print "Peer has closed the session"
                break
            else:
                if buf.strip().lower() == 'quit':
                    print "Got quit command, closing connection"
                    session.bye()
                    break
            session.send(buf)
        except Exception, e:
            print "Error in reception: ", e
            break
session.shutdown()
session.close()