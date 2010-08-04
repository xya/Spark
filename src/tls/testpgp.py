#!/usr/bin/env python

from ctypes import *
from gnutls.library.functions import *
from gnutls.library.types import *
from gnutls.library.constants import *
from Crypto.Util.number import bytes_to_long, long_to_bytes

def create_datum(size=0):
    datum = gnutls_datum_t()
    if size > 0:
        buffer = create_string_buffer(size)
        datum.data = cast(buffer, POINTER(c_ubyte))
        datum.size = size
    else:
        datum.data = cast(c_char_p(), POINTER(c_ubyte))
        datum.size = 0
    return datum

def bytes_to_datum(b):
    datum = gnutls_datum_t()
    datum.data = cast(c_char_p(b), POINTER(c_ubyte))
    datum.size = len(b)
    return datum

def datum_to_bytes(datum):
    return bytearray(datum.data[0:datum.size])

def unwrap(o, c_type):
    if isinstance(o, c_type):
        return o
    elif hasattr(o, "_c_obj"):
        _c_obj = getattr(o, "_c_obj")
        if isinstance(_c_obj, c_type):
            return _c_obj
    raise TypeError("%s object can't be converted to %s" % (o.__class__.__name__, c_type.__name__))

class OpenPGPCertificate(object):
    """ Contains an OpenPGP public key. """
    def __init__(self):
        self._c_obj = gnutls_openpgp_crt_t()
        gnutls_openpgp_crt_init(self._c_obj)
    
    def __del__(self):
        gnutls_openpgp_crt_deinit(self._c_obj)
        del self._c_obj
    
    @classmethod
    def from_bytes(cls, b, raw=False):
        if raw:
            format = GNUTLS_OPENPGP_FMT_RAW
        else:
            format = GNUTLS_OPENPGP_FMT_BASE64
        pub = cls()
        gnutls_openpgp_crt_import(pub._c_obj, bytes_to_datum(b), format)
        return pub
    
    @property
    def id(self):
        keyid = gnutls_openpgp_keyid_t()
        gnutls_openpgp_crt_get_key_id(self._c_obj, keyid)
        return "".join([hex(b)[2:] for b in keyid])
    
    def values(self):
        m = gnutls_datum_t()
        e = gnutls_datum_t()
        gnutls_openpgp_crt_get_pk_rsa_raw(self._c_obj, m, e)
        return {'m': datum_to_bytes(m), 'e': datum_to_bytes(e)}
    
    def __str__(self):
        d = gnutls_datum_t()
        # XXX find a way to free d's memory
        gnutls_openpgp_crt_print(self._c_obj, GNUTLS_CRT_PRINT_FULL, d)
        return datum_to_bytes(d).decode('latin1')

class OpenPGPPrivateKey(object):
    """ Contains an OpenPGP private key. """
    def __init__(self):
        self._c_obj = gnutls_openpgp_privkey_t()
        gnutls_openpgp_privkey_init(self._c_obj)
    
    def __del__(self):
        gnutls_openpgp_privkey_deinit(self._c_obj)
        del self._c_obj
    
    @classmethod
    def from_bytes(cls, b, raw=False):
        if raw:
            format = GNUTLS_OPENPGP_FMT_RAW
        else:
            format = GNUTLS_OPENPGP_FMT_BASE64
        priv = cls()
        gnutls_openpgp_privkey_import(priv._c_obj, bytes_to_datum(b), format, c_char_p(), 0)
        return priv
    
    @property
    def id(self):
        keyid = gnutls_openpgp_keyid_t()
        gnutls_openpgp_privkey_get_key_id(self._c_obj, keyid)
        return "".join([hex(b)[2:] for b in keyid])
    
    @property
    def info(self):
        key_size = c_uint()
        algo = gnutls_openpgp_privkey_get_pk_algorithm(self._c_obj, byref(key_size))
        return algo, key_size.value
    
    def values(self):
        m = gnutls_datum_t()
        e = gnutls_datum_t()
        d = gnutls_datum_t()
        p = gnutls_datum_t()
        q = gnutls_datum_t()
        u = gnutls_datum_t()
        gnutls_openpgp_privkey_export_rsa_raw(self._c_obj, m, e, d, p, q, u)
        return {'m': datum_to_bytes(m), 'e': datum_to_bytes(e),
                'd': datum_to_bytes(d), 'p': datum_to_bytes(p),
                'q': datum_to_bytes(q), 'u': datum_to_bytes(u)}

class CertificateCredentials(object):
    def __init__(self):
        self._c_obj = gnutls_certificate_credentials_t()
        gnutls_certificate_allocate_credentials(self._c_obj)
    
    def __del__(self):
        gnutls_certificate_free_credentials(self._c_obj)
        del self._c_obj
    
    @classmethod
    def from_openpgp_key_pair(cls, pub, priv):
        pub_c = unwrap(pub, gnutls_openpgp_crt_t)
        priv_c = unwrap(priv, gnutls_openpgp_privkey_t)
        cred = cls()
        gnutls_certificate_set_openpgp_key(cred._c_obj, pub_c, priv_c)
        return cred