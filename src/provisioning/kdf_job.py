"""Cooperative PBKDF2 job stepper (≤N HMAC rounds per tick).

Host-testable: no ``machine``/``network``/``ntptime``. Coordinator owns at most
one job; wipe password bytearrays on every terminal outcome.
"""

from src import config
from src.provisioning.verifier import (
    DIGEST_LEN,
    PBKDF2_ITERATIONS,
    SALT_LEN,
    bytes_to_hex,
    constant_time_equal,
    hmac_sha256,
    hex_to_bytes,
)

PURPOSE_LOGIN_VERIFY = "login_verify"
PURPOSE_PASSWORD_CHANGE_DERIVE = "password_change_derive"

VERIFY_OK = "VERIFY_OK"
VERIFY_REJECTED = "VERIFY_REJECTED"
VERIFY_INVALID_RECORD = "VERIFY_INVALID_RECORD"
VERIFY_CANCELLED = "VERIFY_CANCELLED"
VERIFY_FAILED = "VERIFY_FAILED"

DERIVE_OK = "DERIVE_OK"
DERIVE_FAILED = "DERIVE_FAILED"
DERIVE_CANCELLED = "DERIVE_CANCELLED"

_TERMINAL = frozenset(
    {
        VERIFY_OK,
        VERIFY_REJECTED,
        VERIFY_INVALID_RECORD,
        VERIFY_CANCELLED,
        VERIFY_FAILED,
        DERIVE_OK,
        DERIVE_FAILED,
        DERIVE_CANCELLED,
    }
)


def _wipe(buf):
    if isinstance(buf, bytearray):
        for i in range(len(buf)):
            buf[i] = 0


class KdfJob:
    """Incremental PBKDF2-HMAC-SHA256 verify or derive for one Admin password."""

    __slots__ = (
        "correlation_id",
        "purpose",
        "_password",
        "_salt",
        "_expected",
        "_iterations",
        "_u",
        "_out",
        "_round",
        "_result",
        "_started",
        "_salt_hex",
        "_verifier_hex",
    )

    def __init__(
        self,
        correlation_id,
        purpose,
        password,
        salt_hex=None,
        verifier_hex=None,
        iterations=None,
        urandom=None,
    ):
        self.correlation_id = correlation_id
        self.purpose = purpose
        self._iterations = (
            PBKDF2_ITERATIONS if iterations is None else int(iterations)
        )
        self._password = None
        self._salt = None
        self._expected = None
        self._u = None
        self._out = None
        self._round = 0
        self._result = None
        self._started = False
        self._salt_hex = None
        self._verifier_hex = None

        if isinstance(password, bytearray):
            self._password = password
        elif isinstance(password, bytes):
            self._password = bytearray(password)
        else:
            self._password = bytearray(str(password).encode("utf-8"))

        if purpose == PURPOSE_PASSWORD_CHANGE_DERIVE:
            self._init_derive(urandom)
        else:
            self._init_verify(salt_hex, verifier_hex)

    def _init_verify(self, salt_hex, verifier_hex):
        try:
            salt = hex_to_bytes(salt_hex)
            expected = hex_to_bytes(verifier_hex)
        except ValueError:
            self._finish(VERIFY_INVALID_RECORD)
            return
        if len(salt) != SALT_LEN or len(expected) != DIGEST_LEN:
            self._finish(VERIFY_INVALID_RECORD)
            return
        if self._iterations < 1:
            self._finish(VERIFY_FAILED)
            return
        self._salt = salt
        self._expected = expected

    def _init_derive(self, urandom):
        if self._iterations < 1:
            self._finish(DERIVE_FAILED)
            return
        if urandom is None:
            import os

            urandom = os.urandom
        try:
            salt = urandom(SALT_LEN)
        except Exception:
            self._finish(DERIVE_FAILED)
            return
        if not isinstance(salt, (bytes, bytearray)) or len(salt) != SALT_LEN:
            self._finish(DERIVE_FAILED)
            return
        self._salt = bytes(salt)
        self._salt_hex = bytes_to_hex(self._salt)

    @property
    def done(self):
        return self._result is not None

    @property
    def result(self):
        return self._result

    @property
    def salt_hex(self):
        """Fresh salt hex after a successful derive (``None`` otherwise)."""
        return self._salt_hex

    @property
    def verifier_hex(self):
        """Derived verifier hex after a successful derive (``None`` otherwise)."""
        return self._verifier_hex

    def step(self, max_rounds=None):
        """
        Advance at most ``max_rounds`` HMAC rounds.

        Returns a terminal result code when finished, else ``None``.
        """
        if self._result is not None:
            return self._result
        budget = (
            config.KDF_ROUNDS_PER_TICK if max_rounds is None else int(max_rounds)
        )
        if budget < 1:
            return None
        fail_code = (
            DERIVE_FAILED
            if self.purpose == PURPOSE_PASSWORD_CHANGE_DERIVE
            else VERIFY_FAILED
        )
        try:
            return self._step(budget)
        except Exception:
            self._finish(fail_code)
            return self._result

    def cancel(self):
        """Abandon the job and wipe secrets."""
        if self._result is not None:
            return self._result
        if self.purpose == PURPOSE_PASSWORD_CHANGE_DERIVE:
            self._finish(DERIVE_CANCELLED)
        else:
            self._finish(VERIFY_CANCELLED)
        return self._result

    def _step(self, budget):
        used = 0
        if not self._started:
            # First HMAC: U1 = HMAC(password, salt || INT(1))
            self._u = hmac_sha256(
                self._password, self._salt + (1).to_bytes(4, "big")
            )
            self._out = bytearray(self._u)
            self._round = 1
            self._started = True
            used = 1
            if self._round >= self._iterations:
                return self._complete()
            if used >= budget:
                return None

        while used < budget and self._round < self._iterations:
            self._u = hmac_sha256(self._password, self._u)
            for i, byte in enumerate(self._u):
                self._out[i] ^= byte
            self._round += 1
            used += 1

        if self._round >= self._iterations:
            return self._complete()
        return None

    def _complete(self):
        if self.purpose == PURPOSE_PASSWORD_CHANGE_DERIVE:
            return self._complete_derive()
        return self._complete_compare()

    def _complete_compare(self):
        actual = bytes(self._out[:DIGEST_LEN])
        matched = constant_time_equal(actual, self._expected)
        self._finish(VERIFY_OK if matched else VERIFY_REJECTED)
        return self._result

    def _complete_derive(self):
        self._verifier_hex = bytes_to_hex(bytes(self._out[:DIGEST_LEN]))
        self._finish(DERIVE_OK)
        return self._result

    def _finish(self, code):
        if self._result is not None:
            return
        if code not in _TERMINAL:
            code = (
                DERIVE_FAILED
                if self.purpose == PURPOSE_PASSWORD_CHANGE_DERIVE
                else VERIFY_FAILED
            )
        # Drop derive outputs on any non-success terminal so callers cannot
        # commit a partial digest after cancel/fail.
        if code != DERIVE_OK:
            self._salt_hex = None
            self._verifier_hex = None
        self._result = code
        _wipe(self._password)
        self._password = None
        self._salt = None
        self._expected = None
        self._u = None
        if isinstance(self._out, bytearray):
            _wipe(self._out)
        self._out = None
