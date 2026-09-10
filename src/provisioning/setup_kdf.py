"""Small first-boot PBKDF2 derive job; loaded while setup scan is active."""

import time

from src.provisioning.constants import SALT_LEN
from src.provisioning.verifier import _hmac_pads, bytes_to_hex, hmac_sha256_pads

_DEFAULT_CLOCK = getattr(time, "monotonic", time.time)

DERIVE_OK = "DERIVE_OK"
DERIVE_FAILED = "DERIVE_FAILED"
DERIVE_CANCELLED = "DERIVE_CANCELLED"


class SetupKdfJob:
    __slots__ = "password", "salt", "u", "out", "round", "iterations", "done", "result", "salt_hex", "verifier_hex", "pads", "clock", "max_step_ms"

    def __init__(self, password, iterations, urandom=None, clock=None, max_step_ms=None):
        if urandom is None:
            import os
            urandom = os.urandom
        self.password = password if isinstance(password, bytearray) else bytearray(password)
        self.salt = None
        self.u = None
        self.out = None
        self.round = 0
        try:
            self.iterations = int(iterations)
        except Exception:
            self.iterations = 0
        self.done = False
        self.result = None
        self.salt_hex = None
        self.verifier_hex = None
        self.pads = None
        self.clock = _DEFAULT_CLOCK if clock is None else clock
        self.max_step_ms = max_step_ms
        try:
            self.salt = urandom(SALT_LEN)
        except Exception:
            self._terminal(DERIVE_FAILED)
            return
        if not isinstance(self.salt, (bytes, bytearray)) or len(self.salt) != SALT_LEN:
            self._terminal(DERIVE_FAILED)
            return
        self.salt = bytes(self.salt)
        try:
            self.pads = _hmac_pads(self.password)
        except Exception:
            self._terminal(DERIVE_FAILED)

    def step(self, budget):
        used = 0
        if self.done:
            return self.result
        try:
            budget = int(budget)
        except Exception:
            self._terminal(DERIVE_FAILED)
            return self.result
        if self.iterations < 1 or budget < 1:
            self._terminal(DERIVE_FAILED)
            return self.result
        try:
            started = self.clock()
            if self.u is None:
                self.u = hmac_sha256_pads(self.pads, self.salt + b"\0\0\0\1")
                self.out = bytearray(self.u)
                self.round = 1
                used = 1
            while used < budget and self.round < self.iterations:
                if self.max_step_ms is not None and used > 0 and (self.clock() - started) * 1000 >= float(self.max_step_ms):
                    break
                self.u = hmac_sha256_pads(self.pads, self.u)
                for index, value in enumerate(self.u):
                    self.out[index] ^= value
                self.round += 1
                used += 1
        except Exception:
            self._terminal(DERIVE_FAILED)
            return self.result
        if self.round >= self.iterations:
            self.salt_hex = bytes_to_hex(self.salt)
            self.verifier_hex = bytes_to_hex(bytes(self.out))
            self._terminal(DERIVE_OK)
            return self.result
        return None

    def cancel(self):
        if not self.done:
            self._terminal(DERIVE_CANCELLED)
        return self.result

    def _terminal(self, result):
        if self.done:
            return
        self.result = result
        self._wipe()
        self.done = True

    def _wipe(self):
        if isinstance(self.password, bytearray):
            for index in range(len(self.password)):
                self.password[index] = 0
        if isinstance(self.out, bytearray):
            for index in range(len(self.out)):
                self.out[index] = 0
        self.u = None
        self.salt = None
        self.out = None
        self.pads = None
