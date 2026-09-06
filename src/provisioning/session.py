"""Bounded in-memory session table (AD-5).

Opaque 16-byte IDs encoded as unpadded base64url (22 chars). Host-testable
with injected ticks/urandom; no device imports.
"""

from src import config
from src.provisioning.verifier import constant_time_equal

SESSION_ID_LEN = 16
SESSION_ID_CHARS = 22
_B64URL_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)
_B64URL_INDEX = {ch: i for i, ch in enumerate(_B64URL_ALPHABET)}


def encode_session_id(raw):
    """Encode 16 raw bytes as unpadded base64url (exactly 22 ASCII chars)."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != SESSION_ID_LEN:
        raise ValueError("session id must be 16 bytes")
    data = bytes(raw)
    out = []
    i = 0
    while i + 3 <= SESSION_ID_LEN:
        n = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        out.append(_B64URL_ALPHABET[(n >> 18) & 63])
        out.append(_B64URL_ALPHABET[(n >> 12) & 63])
        out.append(_B64URL_ALPHABET[(n >> 6) & 63])
        out.append(_B64URL_ALPHABET[n & 63])
        i += 3
    # One leftover byte → two chars (standard ``==`` padding stripped).
    n = data[i] << 16
    out.append(_B64URL_ALPHABET[(n >> 18) & 63])
    out.append(_B64URL_ALPHABET[(n >> 12) & 63])
    text = "".join(out)
    if len(text) != SESSION_ID_CHARS:
        raise ValueError("session id encode length")
    return text


def decode_session_id(text):
    """
    Decode a strict ``[A-Za-z0-9_-]{22}`` session id to 16 bytes.

    Returns ``None`` when the token is malformed.
    """
    if not isinstance(text, str) or len(text) != SESSION_ID_CHARS:
        return None
    for ch in text:
        if ch not in _B64URL_INDEX:
            return None
    # Restore standard padding length (multiple of 4) with zero sextets.
    padded = text + "AA"
    raw = bytearray()
    for i in range(0, 24, 4):
        n = (
            (_B64URL_INDEX[padded[i]] << 18)
            | (_B64URL_INDEX[padded[i + 1]] << 12)
            | (_B64URL_INDEX[padded[i + 2]] << 6)
            | _B64URL_INDEX[padded[i + 3]]
        )
        raw.append((n >> 16) & 0xFF)
        raw.append((n >> 8) & 0xFF)
        raw.append(n & 0xFF)
    return bytes(raw[:SESSION_ID_LEN])


def session_ids_equal(left_text, right_text):
    """Constant-time compare of two encoded session id strings."""
    left = decode_session_id(left_text)
    right = decode_session_id(right_text)
    if left is None or right is None:
        return False
    return constant_time_equal(left, right)


class SessionEntry:
    __slots__ = ("raw_id", "encoded_id", "deadline")

    def __init__(self, raw_id, encoded_id, deadline):
        self.raw_id = raw_id
        self.encoded_id = encoded_id
        self.deadline = deadline


class SessionTable:
    """At most ``SESSION_MAX`` volatile sessions with sliding idle deadlines."""

    def __init__(
        self,
        max_sessions=None,
        idle_ms=None,
        urandom=None,
        ticks_module=None,
    ):
        self._max = (
            config.SESSION_MAX if max_sessions is None else int(max_sessions)
        )
        self._idle_ms = (
            config.SESSION_IDLE_MS if idle_ms is None else int(idle_ms)
        )
        if urandom is None:
            import os

            urandom = os.urandom
        self._urandom = urandom
        if ticks_module is None:
            from src import ticks as ticks_module

        self._ticks = ticks_module
        self._entries = []

    def __len__(self):
        return len(self._entries)

    def expire(self, now):
        """Drop entries whose idle deadline has passed (wrap-safe)."""
        now = int(now)
        kept = []
        for entry in self._entries:
            if self._ticks.ticks_diff(now, entry.deadline) < 0:
                kept.append(entry)
        self._entries = kept

    def is_full(self, now):
        self.expire(now)
        return len(self._entries) >= self._max

    def create(self, now):
        """
        Create a session after expiry sweep.

        Returns the encoded id, or ``None`` when the table is full.
        """
        self.expire(now)
        if len(self._entries) >= self._max:
            return None
        raw = self._urandom(SESSION_ID_LEN)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) != SESSION_ID_LEN:
            raise ValueError("urandom must return 16 bytes")
        raw = bytes(raw)
        encoded = encode_session_id(raw)
        deadline = self._ticks.ticks_add(int(now), self._idle_ms)
        self._entries.append(SessionEntry(raw, encoded, deadline))
        return encoded

    def lookup(self, encoded_id, now):
        """
        Return the matching live entry, or ``None`` if absent/expired/malformed.
        """
        raw = decode_session_id(encoded_id)
        if raw is None:
            return None
        self.expire(now)
        for entry in self._entries:
            if constant_time_equal(entry.raw_id, raw):
                return entry
        return None

    def renew(self, encoded_id, now):
        """Renew idle deadline for a live session; return True on success."""
        entry = self.lookup(encoded_id, now)
        if entry is None:
            return False
        entry.deadline = self._ticks.ticks_add(int(now), self._idle_ms)
        return True

    def keep_only(self, encoded_id, now):
        """
        After expiry sweep, retain only the acting session and renew it.

        Returns True when the acting id was present and kept; otherwise the
        table is emptied and False is returned.
        """
        raw = decode_session_id(encoded_id)
        self.expire(now)
        if raw is None:
            self._entries = []
            return False
        kept = None
        for entry in self._entries:
            if constant_time_equal(entry.raw_id, raw):
                kept = entry
                break
        if kept is None:
            self._entries = []
            return False
        kept.deadline = self._ticks.ticks_add(int(now), self._idle_ms)
        self._entries = [kept]
        return True

    def clear(self):
        self._entries = []
