"""Cooperative PBKDF2 job stepper (≤N HMAC rounds per tick).

Host-testable: no ``machine``/``network``/``ntptime``. Coordinator owns at most
one job; wipe password bytearrays on every terminal outcome.
"""

from src import config
from src.provisioning.verifier import (
    DIGEST_LEN,
    PBKDF2_ITERATIONS,
    SALT_LEN,
    constant_time_equal,
    hmac_sha256,
    hex_to_bytes,
)

PURPOSE_LOGIN_VERIFY = "login_verify"

VERIFY_OK = "VERIFY_OK"
VERIFY_REJECTED = "VERIFY_REJECTED"
VERIFY_INVALID_RECORD = "VERIFY_INVALID_RECORD"
VERIFY_CANCELLED = "VERIFY_CANCELLED"
VERIFY_FAILED = "VERIFY_FAILED"

_TERMINAL = frozenset(
    {
        VERIFY_OK,
        VERIFY_REJECTED,
        VERIFY_INVALID_RECORD,
        VERIFY_CANCELLED,
        VERIFY_FAILED,
    }
)


def _wipe(buf):
    if isinstance(buf, bytearray):
        for i in range(len(buf)):
            buf[i] = 0


class KdfJob:
    """Incremental PBKDF2-HMAC-SHA256 verify for one Admin password attempt."""

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
    )

    def __init__(
        self,
        correlation_id,
        purpose,
        password,
        salt_hex,
        verifier_hex,
        iterations=None,
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

        if isinstance(password, bytearray):
            self._password = password
        elif isinstance(password, bytes):
            self._password = bytearray(password)
        else:
            self._password = bytearray(str(password).encode("utf-8"))

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

    @property
    def done(self):
        return self._result is not None

    @property
    def result(self):
        return self._result

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
        try:
            return self._step(budget)
        except Exception:
            self._finish(VERIFY_FAILED)
            return self._result

    def cancel(self):
        """Abandon the job and wipe secrets."""
        if self._result is not None:
            return self._result
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
                return self._complete_compare()
            if used >= budget:
                return None

        while used < budget and self._round < self._iterations:
            self._u = hmac_sha256(self._password, self._u)
            for i, byte in enumerate(self._u):
                self._out[i] ^= byte
            self._round += 1
            used += 1

        if self._round >= self._iterations:
            return self._complete_compare()
        return None

    def _complete_compare(self):
        actual = bytes(self._out[:DIGEST_LEN])
        matched = constant_time_equal(actual, self._expected)
        self._finish(VERIFY_OK if matched else VERIFY_REJECTED)
        return self._result

    def _finish(self, code):
        if self._result is not None:
            return
        if code not in _TERMINAL:
            code = VERIFY_FAILED
        self._result = code
        _wipe(self._password)
        self._password = None
        self._salt = None
        self._expected = None
        self._u = None
        if isinstance(self._out, bytearray):
            _wipe(self._out)
        self._out = None
