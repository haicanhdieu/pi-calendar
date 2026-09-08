"""Small first-boot PBKDF2 derive job; loaded while setup scan is active."""

from src.provisioning.verifier import SALT_LEN, bytes_to_hex, hmac_sha256

DERIVE_OK = "DERIVE_OK"


class SetupKdfJob:
    __slots__ = "password", "salt", "u", "out", "round", "iterations", "done", "salt_hex", "verifier_hex"

    def __init__(self, password, iterations, urandom=None):
        if urandom is None:
            import os
            urandom = os.urandom
        self.password = password if isinstance(password, bytearray) else bytearray(password)
        self.salt = urandom(SALT_LEN)
        self.u = None
        self.out = None
        self.round = 0
        self.iterations = int(iterations)
        self.done = False
        self.salt_hex = None
        self.verifier_hex = None

    def step(self, budget):
        used = 0
        if self.done:
            return DERIVE_OK
        if self.u is None:
            self.u = hmac_sha256(self.password, self.salt + b"\0\0\0\1")
            self.out = bytearray(self.u)
            self.round = 1
            used = 1
        while used < int(budget) and self.round < self.iterations:
            self.u = hmac_sha256(self.password, self.u)
            for index, value in enumerate(self.u):
                self.out[index] ^= value
            self.round += 1
            used += 1
        if self.round >= self.iterations:
            self.salt_hex = bytes_to_hex(self.salt)
            self.verifier_hex = bytes_to_hex(bytes(self.out))
            self._wipe()
            self.done = True
            return DERIVE_OK
        return None

    def cancel(self):
        self._wipe()

    def _wipe(self):
        if isinstance(self.password, bytearray):
            for index in range(len(self.password)):
                self.password[index] = 0
        if isinstance(self.out, bytearray):
            for index in range(len(self.out)):
                self.out[index] = 0

