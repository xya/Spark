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

class OpenPGPKeyring(object):
    """ Contains multiple OpenPGP certificate. """
    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        instance.__deinit = gnutls_openpgp_keyring_deinit
        instance._c_object = gnutls_openpgp_keyring_t()
        return instance
    
    def __init__(self, data=None, format=OPENPGP_FMT_RAW):
        gnutls_openpgp_keyring_init(self._c_object)
        if data:
            gnutls_openpgp_keyring_import(self._c_object, bytes_to_datum(data), format)
    
    def __del__(self):
        self.__deinit(self._c_object)
    
    @classmethod
    def from_list(cls, certificates):
        blobs = [cert.export(OPENPGP_FMT_RAW) for cert in certificates]
        keyring_blob = "".join(blobs)
        return cls(keyring_blob, OPENPGP_FMT_RAW)
    
    def __len__(self):
        return gnutls_openpgp_keyring_get_crt_count(self._c_object)
    
    def __getitem__(self, index):
        cert = OpenPGPCertificate.__new__(OpenPGPCertificate)
        try:
            gnutls_openpgp_keyring_get_crt(self._c_object, index, cert._c_object)
            return cert
        except GNUTLSError:
            raise IndexError()

class OpenPGPCertificate(object):
    """ Contains an OpenPGP public key. """
    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        instance.__deinit = gnutls_openpgp_crt_deinit
        instance._c_object = gnutls_openpgp_crt_t()
        return instance
    
    def __init__(self, data, format=OPENPGP_FMT_BASE64):
        gnutls_openpgp_crt_init(self._c_object)
        gnutls_openpgp_crt_import(self._c_object, bytes_to_datum(data), format)
    
    def __del__(self):
        self.__deinit(self._c_object)
    
    def export(self, format=OPENPGP_FMT_BASE64):
        buf_size = c_size_t()
        try:
            gnutls_openpgp_crt_export(self._c_object, format, '', byref(buf_size))
        except MemoryError:
            pass
        buf = create_string_buffer(buf_size.value)
        gnutls_openpgp_crt_export(self._c_object, format, buf, byref(buf_size))
        return string_at(buf, buf_size.value)
    
    @method_args(OpenPGPKeyring)
    def verify(self, keyring):
        status = c_uint()
        gnutls_openpgp_crt_verify_ring(self._c_object, keyring._c_object, 0, byref(status))
        verify_cert_status(status.value)
    
    def verify_self(self):
        status = c_uint()
        gnutls_openpgp_crt_verify_self(self._c_object, 0, byref(status))
        verify_cert_status(status.value)
    
    @property
    def id(self):
        keyid = gnutls_openpgp_keyid_t()
        gnutls_openpgp_crt_get_key_id(self._c_object, keyid)
        return "".join([hex(b)[2:] for b in keyid])
    
    @property
    def fingerprint(self):
        buf_size = c_size_t(20)
        buf = create_string_buffer(buf_size.value)
        gnutls_openpgp_crt_get_fingerprint(self._c_object, buf, byref(buf_size))
        return "".join([hex(ord(b))[2:] for b in string_at(buf, buf_size.value)])
    
    @property
    def name(self):
        buf_size = c_size_t()
        try:
            gnutls_openpgp_crt_get_name(self._c_object, 0, '', byref(buf_size))
        except MemoryError:
            pass
        buf = create_string_buffer(buf_size.value)
        gnutls_openpgp_crt_get_name(self._c_object, 0, buf, byref(buf_size))
        return string_at(buf, buf_size.value)
    
    @property
    def creation_time(self):
        t = gnutls_openpgp_crt_get_creation_time(self._c_object)
        if t > 0:
            return datetime.datetime.fromtimestamp(t)
        else:
            return None
    
    @property
    def expiration_time(self):
        t = gnutls_openpgp_crt_get_expiration_time(self._c_object)
        if t > 0:
            return datetime.datetime.fromtimestamp(t)
        else:
            return None
    
    def values(self):
        m = gnutls_datum_t()
        e = gnutls_datum_t()
        gnutls_openpgp_crt_get_pk_rsa_raw(self._c_object, m, e)
        return {'m': datum_to_bytes(m), 'e': datum_to_bytes(e)}
    
    def __str__(self):
        d = gnutls_datum_t()
        # XXX find a way to free d's memory
        gnutls_openpgp_crt_print(self._c_object, GNUTLS_CRT_PRINT_FULL, d)
        return datum_to_bytes(d).decode('latin1')

class OpenPGPPrivateKey(object):
    """ Contains an OpenPGP private key. """
    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        instance.__deinit = gnutls_openpgp_privkey_deinit
        instance._c_object = gnutls_openpgp_privkey_t()
        return instance
    
    def __init__(self, data, format=OPENPGP_FMT_BASE64):
        gnutls_openpgp_privkey_init(self._c_object)
        gnutls_openpgp_privkey_import(self._c_object, bytes_to_datum(data), format, c_char_p(), 0)
    
    def __del__(self):
        self.__deinit(self._c_object)
    
    @property
    def id(self):
        keyid = gnutls_openpgp_keyid_t()
        gnutls_openpgp_privkey_get_key_id(self._c_object, keyid)
        return "".join([hex(b)[2:] for b in keyid])
    
    @property
    def info(self):
        key_size = c_uint()
        algo = gnutls_openpgp_privkey_get_pk_algorithm(self._c_object, byref(key_size))
        return algo, key_size.value
    
    def values(self):
        # XXX This assumes RSA keys
        m = gnutls_datum_t()
        e = gnutls_datum_t()
        d = gnutls_datum_t()
        p = gnutls_datum_t()
        q = gnutls_datum_t()
        u = gnutls_datum_t()
        gnutls_openpgp_privkey_export_rsa_raw(self._c_object, m, e, d, p, q, u)
        return {'m': datum_to_bytes(m), 'e': datum_to_bytes(e),
                'd': datum_to_bytes(d), 'p': datum_to_bytes(p),
                'q': datum_to_bytes(q), 'u': datum_to_bytes(u)}