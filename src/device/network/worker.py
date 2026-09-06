"""Isolated network worker shell (AD-8 device boundary).

Owns ``_thread`` locking around mailbox take/publish. Network operations are
injected so the proof harness can stub DNS/NTP success and failure without
calling ``ntptime.settime()`` or touching RTC, TFT, or ``AppState``.
"""

import _thread

from src.device.network.mailbox import MailboxSaturationError, SyncResult
from src.ticks import ticks_diff, ticks_ms


class NetworkWorker:
    """
    One background thread that consumes SyncCommands and publishes SyncResults.

    Callers must supply the shared mailbox, one ``_thread.allocate_lock``, and
    an ops object with ``run(command) -> SyncResult``.
    """

    def __init__(self, mailbox, lock, ops, log=None, poll_delay_ms=5):
        self._mailbox = mailbox
        self._lock = lock
        self._ops = ops
        self._log = log if log is not None else print
        self._poll_delay_ms = poll_delay_ms
        self._running = False
        self.fatal = None

    def start(self):
        """Start the worker thread. Idempotent if already running."""
        if self._running:
            return
        self._running = True
        _thread.start_new_thread(self._loop, ())

    def stop(self):
        """Request the worker loop to exit (best-effort; no join on MP)."""
        self._running = False

    def set_ops(self, ops):
        """Replace injectable network ops (proof scenario switching)."""
        self._ops = ops

    def _loop(self):
        while self._running:
            taken = self._take_command()
            if taken is None:
                self._sleep_ms(self._poll_delay_ms)
                continue
            command, take_epoch = taken
            result = self._run_ops(command)
            self._publish(result, take_epoch)

    def _take_command(self):
        self._lock.acquire()
        try:
            return self._mailbox.try_take_command()
        finally:
            self._lock.release()

    def _deadline_result(self, command):
        return SyncResult(command.command_id, False, None, "deadline")

    def _past_deadline(self, command):
        return ticks_diff(ticks_ms(), command.deadline_ms) >= 0

    def _run_ops(self, command):
        if self._past_deadline(command):
            return self._deadline_result(command)
        try:
            result = self._ops.run(command)
        except Exception as exc:  # noqa: BLE001 — worker must always publish
            self._log("PROOF:WORKER_OPS_ERROR", repr(exc))
            return SyncResult(
                command.command_id,
                False,
                None,
                "ops_error",
            )
        if self._past_deadline(command):
            return self._deadline_result(command)
        if result is None:
            return SyncResult(
                command.command_id,
                False,
                None,
                "ops_empty",
            )
        return result

    def _publish(self, result, take_epoch):
        self._lock.acquire()
        try:
            try:
                self._mailbox.publish_result(result, take_epoch)
            except MailboxSaturationError as exc:
                self.fatal = exc
                self._log(
                    "FATAL:MAILBOX_SATURATION",
                    "result slot occupied; prior result untouched",
                )
        finally:
            self._lock.release()

    @staticmethod
    def _sleep_ms(ms):
        try:
            from time import sleep_ms

            sleep_ms(ms)
        except ImportError:
            from time import sleep

            sleep(ms / 1000.0)
