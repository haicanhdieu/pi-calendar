"""Salted Admin verifier helpers (PBKDF2-HMAC-SHA256).

Host- and MicroPython-safe: uses only ``hashlib.sha256``. Never retains
plaintext passwords beyond the call that derives or verifies them.
"""

import hashlib

from src import config

ADMIN_VERIFIER_VERSION = "pbkdf2-sha256-v1"
PBKDF2_ITERATIONS = config.ADMIN_PBKDF2_ITERATIONS
SALT_LEN = 16
DIGEST_LEN = 32

_HMAC_BLOCK = 64


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return str(value).encode("utf-8")


def hmac_sha256(key, message):
    """RFC 2104 HMAC-SHA256."""
    key = _to_bytes(key)
    message = _to_bytes(message)
    if len(key) > _HMAC_BLOCK:
        key = hashlib.sha256(key).digest()
    if len(key) < _HMAC_BLOCK:
        key = key + (b"\x00" * (_HMAC_BLOCK - len(key)))
    o_key = bytes(b ^ 0x5C for b in key)
    i_key = bytes(b ^ 0x36 for b in key)
    inner = hashlib.sha256(i_key + message).digest()
    return hashlib.sha256(o_key + inner).digest()


def pbkdf2_hmac_sha256(password, salt, iterations=PBKDF2_ITERATIONS, dklen=DIGEST_LEN):
    """RFC 2898 PBKDF2 with HMAC-SHA256 (portable; no hashlib.pbkdf2_hmac)."""
    password = _to_bytes(password)
    salt = _to_bytes(salt)
    iterations = int(iterations)
    dklen = int(dklen)
    if iterations < 1 or dklen < 1:
        raise ValueError("invalid PBKDF2 parameters")
    hash_len = DIGEST_LEN
    blocks = []
    block_index = 1
    while len(b"".join(blocks)) < dklen:
        u = hmac_sha256(password, salt + block_index.to_bytes(4, "big"))
        out = bytearray(u)
        for _ in range(1, iterations):
            u = hmac_sha256(password, u)
            for i, byte in enumerate(u):
                out[i] ^= byte
        blocks.append(bytes(out))
        block_index += 1
    return b"".join(blocks)[:dklen]


def bytes_to_hex(data):
    """Lowercase hexadecimal encoding."""
    return "".join("{:02x}".format(b) for b in data)


def hex_to_bytes(text):
    """Decode lowercase/mixed hex to bytes; raises ValueError on bad input."""
    if not isinstance(text, str) or len(text) % 2:
        raise ValueError("invalid hex")
    try:
        return bytes(int(text[i : i + 2], 16) for i in range(0, len(text), 2))
    except ValueError as exc:
        raise ValueError("invalid hex") from exc


def constant_time_equal(left, right):
    """Constant-time equality for equal-length byte strings."""
    left = _to_bytes(left)
    right = _to_bytes(right)
    if len(left) != len(right):
        return False
    diff = 0
    for a, b in zip(left, right):
        diff |= a ^ b
    return diff == 0


def derive_admin_verifier(password, salt=None, urandom=None, iterations=PBKDF2_ITERATIONS):
    """
    Derive ``(salt_hex, verifier_hex)`` for an Admin password.

    ``salt`` may be 16 raw bytes; otherwise ``urandom(16)`` supplies it.
    """
    if salt is None:
        if urandom is None:
            import os

            urandom = os.urandom
        salt = urandom(SALT_LEN)
    salt = _to_bytes(salt)
    if len(salt) != SALT_LEN:
        raise ValueError("salt must be 16 bytes")
    digest = pbkdf2_hmac_sha256(
        _to_bytes(password), salt, iterations=iterations, dklen=DIGEST_LEN
    )
    return bytes_to_hex(salt), bytes_to_hex(digest)


def verify_admin_password(
    password, salt_hex, verifier_hex, iterations=PBKDF2_ITERATIONS
):
    """Return True when password matches the stored salted verifier."""
    try:
        salt = hex_to_bytes(salt_hex)
        expected = hex_to_bytes(verifier_hex)
    except ValueError:
        return False
    if len(salt) != SALT_LEN or len(expected) != DIGEST_LEN:
        return False
    actual = pbkdf2_hmac_sha256(
        _to_bytes(password), salt, iterations=iterations, dklen=DIGEST_LEN
    )
    return constant_time_equal(actual, expected)
