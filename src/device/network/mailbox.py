"""Pure capacity-one sync mailbox protocol (AD-8).

Lock-free protocol object: App and the network worker must call these methods
only while holding the shared external lock. Host tests drive the protocol with
plain call sequencing; the device worker uses ``_thread.allocate_lock``.

Forbidden imports: ``machine``, ``network``, ``ntptime``, ``_thread``.
"""

from src.ticks import ticks_diff


class MailboxSaturationError(Exception):
    """Result slot still occupied — contract violation (never overwrite)."""


class SyncCommand:
    """One bounded sync request from App to the network worker."""

    __slots__ = ("command_id", "deadline_ms")

    def __init__(self, command_id, deadline_ms):
        self.command_id = command_id
        self.deadline_ms = deadline_ms

    def __eq__(self, other):
        if not isinstance(other, SyncCommand):
            return NotImplemented
        return (
            self.command_id == other.command_id
            and self.deadline_ms == other.deadline_ms
        )

    def __repr__(self):
        return "SyncCommand(command_id={!r}, deadline_ms={!r})".format(
            self.command_id, self.deadline_ms
        )


class SyncResult:
    """Terminal worker outcome for one SyncCommand."""

    __slots__ = ("command_id", "ok", "utc", "error_code")

    def __init__(self, command_id, ok, utc, error_code):
        self.command_id = command_id
        self.ok = ok
        self.utc = utc
        self.error_code = error_code

    def __eq__(self, other):
        if not isinstance(other, SyncResult):
            return NotImplemented
        return (
            self.command_id == other.command_id
            and self.ok == other.ok
            and self.utc == other.utc
            and self.error_code == other.error_code
        )

    def __repr__(self):
        return (
            "SyncResult(command_id={!r}, ok={!r}, utc={!r}, error_code={!r})"
        ).format(self.command_id, self.ok, self.utc, self.error_code)


class Mailbox:
    """
    Separate capacity-one command and result slots plus an idle flag.

    Enqueue only while idle; publish exactly one terminal result into an empty
    result slot; never overwrite. Soft reset clears both slots to idle/empty
    and bumps an epoch so in-flight publishes are discarded as orphans.
    """

    __slots__ = ("_command", "_result", "_idle", "_epoch")

    def __init__(self):
        self._command = None
        self._result = None
        self._idle = True
        self._epoch = 0

    @property
    def idle(self):
        return self._idle

    @property
    def epoch(self):
        return self._epoch

    @property
    def has_command(self):
        return self._command is not None

    @property
    def has_result(self):
        return self._result is not None

    def enqueue(self, command):
        """
        Accept a SyncCommand only while idle, command slot empty, and result
        slot empty (retry waits for prior-result consumption).

        On accept, marks the worker non-idle. Returns True if accepted, False
        if rejected (non-blocking; never overwrites an in-flight command).
        """
        if not self._idle or self._command is not None or self._result is not None:
            return False
        self._command = command
        self._idle = False
        return True

    def try_take_command(self):
        """
        Worker atomically takes the pending command, or None if empty.

        On take, returns ``(command, take_epoch)`` so ``publish_result`` can
        discard orphans after a soft_reset epoch bump.
        """
        command = self._command
        if command is None:
            return None
        self._command = None
        return (command, self._epoch)

    def publish_result(self, result, take_epoch):
        """
        Publish exactly one terminal SyncResult into an empty result slot.

        If ``take_epoch`` does not match the current epoch (soft_reset since
        take), discard with no write and return False. Marks idle on success.
        Raises MailboxSaturationError if the result slot holds a live result.
        """
        if take_epoch != self._epoch:
            return False
        if self._result is not None:
            raise MailboxSaturationError(
                "result slot occupied; refusing overwrite"
            )
        self._result = result
        self._idle = True
        return True

    def occupy_result(self, result):
        """
        Occupy the result slot without changing idle (proof contention plant).

        Raises MailboxSaturationError if the slot is already occupied.
        """
        if self._result is not None:
            raise MailboxSaturationError(
                "result slot occupied; refusing overwrite"
            )
        self._result = result

    def try_take_result(self):
        """App consumes the pending result, or None if empty."""
        result = self._result
        if result is None:
            return None
        self._result = None
        return result

    def soft_reset(self):
        """Clear both slots, restore idle, and bump epoch (orphan publishes)."""
        self._command = None
        self._result = None
        self._idle = True
        self._epoch += 1


def result_is_expired(deadline_ms, now_ms):
    """True when ``now_ms`` is at or past ``deadline_ms`` (wrap-safe ticks)."""
    return ticks_diff(now_ms, deadline_ms) >= 0


def should_apply_result(result, expected_command_id, deadline_ms, now_ms):
    """
    Consumer gate: apply only a matching, non-expired result.

    Mismatch or expiry → discard (do not apply). Caller must still have
    consumed the result from the slot.
    """
    if result is None:
        return False
    if result.command_id != expected_command_id:
        return False
    if result_is_expired(deadline_ms, now_ms):
        return False
    return True
