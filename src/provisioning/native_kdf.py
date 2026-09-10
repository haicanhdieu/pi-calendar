"""Native-emitted PBKDF2-HMAC-SHA256 fast path for MicroPython.

This module keeps the wire/storage contract identical to the portable Python
implementation.  Deploy it as an ARMv6-M native .mpy on RP2040; CPython uses
the same function as a correctness/reference path in host tests.
"""

import hashlib


def _hmac_sha256(inner_pad, outer_pad, message):
    inner = hashlib.sha256()
    inner.update(inner_pad)
    inner.update(message)
    digest = inner.digest()
    outer = hashlib.sha256()
    outer.update(outer_pad)
    outer.update(digest)
    return outer.digest()


class Pbkdf2Job:
    """Incremental native-emitted PBKDF2 job for one 32-byte block."""

    def __init__(self, password, salt, iterations):
        password = bytes(password)
        self.salt = bytes(salt)
        self.iterations = int(iterations)
        self.round = 0
        self.current = None
        self.output = None
        if self.iterations < 1 or len(self.salt) < 1:
            raise ValueError("invalid PBKDF2 parameters")
        if len(password) > 64:
            password = hashlib.sha256(password).digest()
        password = password + (b"\x00" * (64 - len(password)))
        self.inner_pad = bytes(value ^ 0x36 for value in password)
        self.outer_pad = bytes(value ^ 0x5C for value in password)

    def step(self, max_rounds):
        """Run at most max_rounds and return the digest only at completion."""
        budget = int(max_rounds)
        if budget < 1:
            return None
        used = 0
        if self.round == 0:
            self.current = _hmac_sha256(
                self.inner_pad, self.outer_pad, self.salt + b"\x00\x00\x00\x01"
            )
            self.output = bytearray(self.current)
            self.round = 1
            used = 1
        while used < budget and self.round < self.iterations:
            self.current = _hmac_sha256(
                self.inner_pad, self.outer_pad, self.current
            )
            for index, value in enumerate(self.current):
                self.output[index] ^= value
            self.round += 1
            used += 1
        if self.round >= self.iterations:
            return bytes(self.output)
        return None


def pbkdf2_hmac_sha256(password, salt, iterations, dklen=32):
    """Return PBKDF2-HMAC-SHA256 output for one 32-byte block."""
    password = bytes(password)
    salt = bytes(salt)
    iterations = int(iterations)
    dklen = int(dklen)
    if iterations < 1 or dklen < 1 or dklen > 32:
        raise ValueError("invalid PBKDF2 parameters")
    return Pbkdf2Job(password, salt, iterations).step(iterations)[:dklen]
