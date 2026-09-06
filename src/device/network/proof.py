"""Flashable AD-8 network mailbox proof harness (Story 1.4).

Exercises success/fail DNS/NTP stubs, result-slot contention, stale/expired
results, retry sequencing, soft reset, render-continuity polling while the
worker is busy, and sustained lock iterations. Emits serial markers for the
user evidence checklist in ``proof-1-4-network-mailbox.md``.

Never calls ``ntptime.settime()``. Never touches RTC, TFT, or ``AppState``.
Device observation rows must be filled by a human after flash — not by host CI.
"""

from src import config
from src import ticks
from src.device.network.mailbox import (
    Mailbox,
    SyncCommand,
    SyncResult,
    should_apply_result,
)
from src.device.network.worker import NetworkWorker
from src.time.model import DateTime


def _sleep_ms(ms):
    try:
        from time import sleep_ms

        sleep_ms(ms)
    except ImportError:
        from time import sleep

        sleep(ms / 1000.0)


def _log(*parts):
    print(" ".join(str(p) for p in parts))


def _allocate_lock():
    import _thread

    return _thread.allocate_lock()


def _mem_free():
    """Return free heap bytes when ``gc.mem_free`` exists (MicroPython)."""
    try:
        import gc

        mem_free = getattr(gc, "mem_free", None)
        if callable(mem_free):
            return mem_free()
    except Exception:  # noqa: BLE001 — optional on host
        return None
    return None


class StubOps:
    """Injectable DNS/NTP stubs for proof scenarios (no real WLAN)."""

    def __init__(self, mode="success", delay_ms=0, utc=None):
        self.mode = mode
        self.delay_ms = delay_ms
        self.utc = utc if utc is not None else DateTime(2026, 9, 6, 6, 12, 0, 0)
        self.calls = 0

    def run(self, command):
        self.calls += 1
        if self.delay_ms:
            remaining = self.delay_ms
            chunk = 50
            while remaining > 0:
                if ticks.ticks_diff(ticks.ticks_ms(), command.deadline_ms) >= 0:
                    return SyncResult(command.command_id, False, None, "deadline")
                step = chunk if remaining > chunk else remaining
                _sleep_ms(step)
                remaining -= step
        if ticks.ticks_diff(ticks.ticks_ms(), command.deadline_ms) >= 0:
            return SyncResult(command.command_id, False, None, "deadline")
        mode = self.mode
        if mode == "success":
            return SyncResult(command.command_id, True, self.utc, None)
        if mode == "dns_fail":
            return SyncResult(command.command_id, False, None, "dns_fail")
        if mode == "ntp_fail":
            return SyncResult(command.command_id, False, None, "ntp_fail")
        return SyncResult(command.command_id, False, None, "unknown_mode")


def _with_lock(lock, fn):
    lock.acquire()
    try:
        return fn()
    finally:
        lock.release()


def _enqueue(mailbox, lock, command):
    return _with_lock(lock, lambda: mailbox.enqueue(command))


def _take_result(mailbox, lock):
    return _with_lock(lock, lambda: mailbox.try_take_result())


def _is_clean(mailbox):
    return mailbox.idle and not mailbox.has_command and not mailbox.has_result


def _wait_clean(mailbox, lock, timeout_ms, poll_ms=20):
    deadline = ticks.ticks_add(ticks.ticks_ms(), timeout_ms)
    while ticks.ticks_diff(deadline, ticks.ticks_ms()) > 0:
        if _with_lock(lock, lambda: _is_clean(mailbox)):
            return True
        _sleep_ms(poll_ms)
    return False


def _wait_result(mailbox, lock, timeout_ms, poll_ms=20):
    deadline = ticks.ticks_add(ticks.ticks_ms(), timeout_ms)
    while ticks.ticks_diff(deadline, ticks.ticks_ms()) > 0:
        result = _take_result(mailbox, lock)
        if result is not None:
            return result
        _sleep_ms(poll_ms)
    _with_lock(lock, mailbox.soft_reset)
    return None


def _wait_idle(mailbox, lock, timeout_ms, poll_ms=20):
    deadline = ticks.ticks_add(ticks.ticks_ms(), timeout_ms)
    while ticks.ticks_diff(deadline, ticks.ticks_ms()) > 0:
        if _with_lock(lock, lambda: mailbox.idle):
            return True
        _sleep_ms(poll_ms)
    return False


def _marker(name, outcome, detail=""):
    suffix = (" " + detail) if detail else ""
    _log("PROOF:" + outcome, name + suffix)


def scenario_success_dns_ntp(mailbox, lock, worker, ops):
    name = "success_dns_ntp"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = 0
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    cmd = SyncCommand(1, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    if result is None:
        _marker(name, "FAIL", "timeout")
        return False
    ok = (
        result.command_id == 1
        and result.ok is True
        and result.utc is not None
        and result.error_code is None
    )
    _marker(name, "PASS" if ok else "FAIL", repr(result))
    return ok


def scenario_fail_dns(mailbox, lock, worker, ops):
    name = "fail_dns"
    _log("PROOF:BEGIN", name)
    ops.mode = "dns_fail"
    ops.delay_ms = 0
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    cmd = SyncCommand(2, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    if result is None:
        _marker(name, "FAIL", "timeout")
        return False
    ok = result.ok is False and result.error_code == "dns_fail" and result.utc is None
    _marker(name, "PASS" if ok else "FAIL", repr(result))
    return ok


def scenario_fail_ntp(mailbox, lock, worker, ops):
    name = "fail_ntp"
    _log("PROOF:BEGIN", name)
    ops.mode = "ntp_fail"
    ops.delay_ms = 0
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    cmd = SyncCommand(3, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    if result is None:
        _marker(name, "FAIL", "timeout")
        return False
    ok = result.ok is False and result.error_code == "ntp_fail" and result.utc is None
    _marker(name, "PASS" if ok else "FAIL", repr(result))
    return ok


def scenario_result_contention(mailbox, lock, worker, ops):
    name = "result_slot_contention"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = config.PROOF_BUSY_OP_MS
    worker.set_ops(ops)
    cmd = SyncCommand(
        91, ticks.ticks_add(ticks.ticks_ms(), config.SYNC_COMMAND_DEADLINE_MS)
    )
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    # Wait until the worker takes the command (slot empty, still busy).
    take_deadline = ticks.ticks_add(ticks.ticks_ms(), config.PROOF_RESULT_TIMEOUT_MS)
    taken = False
    while ticks.ticks_diff(take_deadline, ticks.ticks_ms()) > 0:
        if not _with_lock(lock, lambda: mailbox.has_command):
            taken = True
            break
        _sleep_ms(10)
    if not taken:
        _with_lock(lock, mailbox.soft_reset)
        ops.delay_ms = 0
        _marker(name, "FAIL", "worker_did_not_take")
        return False
    # Plant without marking idle (worker still in ops).
    planted = SyncResult(90, False, None, "planted")
    try:
        _with_lock(lock, lambda: mailbox.occupy_result(planted))
    except Exception as exc:  # noqa: BLE001
        _with_lock(lock, mailbox.soft_reset)
        ops.delay_ms = 0
        _marker(name, "FAIL", "plant_failed=%s" % repr(exc))
        return False
    fatal_deadline = ticks.ticks_add(ticks.ticks_ms(), config.PROOF_RESULT_TIMEOUT_MS)
    saw_fatal = False
    while ticks.ticks_diff(fatal_deadline, ticks.ticks_ms()) > 0:
        if worker.fatal is not None:
            saw_fatal = True
            break
        _sleep_ms(20)
    prior = _take_result(mailbox, lock)
    prior_ok = (
        prior is not None
        and prior.command_id == 90
        and prior.error_code == "planted"
    )
    _with_lock(lock, mailbox.soft_reset)
    worker.fatal = None
    ops.delay_ms = 0
    ok = saw_fatal and prior_ok
    _marker(
        name,
        "PASS" if ok else "FAIL",
        "fatal=%s prior_ok=%s" % (saw_fatal, prior_ok),
    )
    return ok


def scenario_stale_expired(mailbox, lock, worker, ops):
    name = "stale_expired_results"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = 0
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    # Expired: deadline already in the past relative to apply-time.
    expired_deadline = ticks.ticks_add(now, -1)
    cmd = SyncCommand(4, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    if result is None:
        _marker(name, "FAIL", "timeout")
        return False
    apply_expired = should_apply_result(result, 4, expired_deadline, ticks.ticks_ms())
    # Stale / mismatched id
    mismatch = SyncResult(999, True, DateTime(2026, 1, 1, 4, 0, 0, 0), None)
    apply_mismatch = should_apply_result(
        mismatch, 4, ticks.ticks_add(ticks.ticks_ms(), 60_000), ticks.ticks_ms()
    )
    ok = (apply_expired is False) and (apply_mismatch is False)
    _marker(
        name,
        "PASS" if ok else "FAIL",
        "expired_apply=%s mismatch_apply=%s" % (apply_expired, apply_mismatch),
    )
    return ok


def scenario_retry_sequencing(mailbox, lock, worker, ops):
    name = "retry_sequencing"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = 0
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    first = SyncCommand(5, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, first):
        _marker(name, "FAIL", "first_enqueue_rejected")
        return False
    # Retry while in-flight / before consume must fail.
    retry_early = SyncCommand(6, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    early_ok = _enqueue(mailbox, lock, retry_early)
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    if result is None:
        _marker(name, "FAIL", "timeout")
        return False
    # Still must not enqueue until idle after consume (result already taken → idle).
    if not _wait_idle(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS):
        _marker(name, "FAIL", "not_idle_after_consume")
        return False
    retry = SyncCommand(7, ticks.ticks_add(ticks.ticks_ms(), config.SYNC_COMMAND_DEADLINE_MS))
    retry_ok = _enqueue(mailbox, lock, retry)
    second = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    ok = (
        early_ok is False
        and retry_ok is True
        and second is not None
        and second.command_id == 7
    )
    _marker(
        name,
        "PASS" if ok else "FAIL",
        "early=%s retry=%s second_id=%s"
        % (early_ok, retry_ok, None if second is None else second.command_id),
    )
    return ok


def scenario_soft_reset(mailbox, lock, worker, ops):
    name = "soft_reset"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    # Long busy op so we can interrupt mid-flight.
    ops.delay_ms = config.PROOF_BUSY_OP_MS
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    cmd = SyncCommand(8, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    _sleep_ms(50)
    _with_lock(lock, mailbox.soft_reset)
    # Epoch discard drops late publishes; wait until empty + idle before follow-up.
    if not _wait_clean(mailbox, lock, config.PROOF_BUSY_OP_MS + 2000):
        _marker(name, "FAIL", "not_clean_after_soft_reset")
        return False
    ops.delay_ms = 0
    worker.set_ops(ops)
    worker.fatal = None
    follow = SyncCommand(9, ticks.ticks_add(ticks.ticks_ms(), config.SYNC_COMMAND_DEADLINE_MS))
    follow_ok = _enqueue(mailbox, lock, follow)
    result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
    ok = follow_ok is True and result is not None and result.command_id == 9
    _marker(name, "PASS" if ok else "FAIL", "follow_ok=%s" % follow_ok)
    return ok


def scenario_render_continuity(mailbox, lock, worker, ops):
    name = "render_continuity"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = config.PROOF_BUSY_OP_MS
    worker.set_ops(ops)
    now = ticks.ticks_ms()
    cmd = SyncCommand(10, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
    if not _enqueue(mailbox, lock, cmd):
        _marker(name, "FAIL", "enqueue_rejected")
        return False
    polls = 0
    got = None
    deadline = ticks.ticks_add(ticks.ticks_ms(), config.PROOF_BUSY_OP_MS + 2000)
    while ticks.ticks_diff(deadline, ticks.ticks_ms()) > 0:
        polls += 1
        got = _take_result(mailbox, lock)
        if got is not None:
            break
        # Simulated render tick — must not sleep on WLAN.
        _sleep_ms(config.PROOF_RENDER_POLL_MS)
    if got is None:
        _with_lock(lock, mailbox.soft_reset)
    ok = got is not None and polls >= config.PROOF_RENDER_MIN_POLLS
    _log("PROOF:MARKER", "poll_count=%d" % polls)
    _marker(name, "PASS" if ok else "FAIL", "polls=%d" % polls)
    ops.delay_ms = 0
    return ok


def scenario_sustained_lock(mailbox, lock, worker, ops):
    name = "sustained_lock_memory"
    _log("PROOF:BEGIN", name)
    ops.mode = "success"
    ops.delay_ms = 0
    worker.set_ops(ops)
    mem_start = _mem_free()
    if mem_start is not None:
        _log("PROOF:MARKER", "mem_free_start=%d" % mem_start)
    failures = 0
    for i in range(config.PROOF_SUSTAINED_ITERATIONS):
        cmd_id = 1000 + i
        now = ticks.ticks_ms()
        cmd = SyncCommand(cmd_id, ticks.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS))
        if not _enqueue(mailbox, lock, cmd):
            failures += 1
            continue
        result = _wait_result(mailbox, lock, config.PROOF_RESULT_TIMEOUT_MS)
        if result is None or result.command_id != cmd_id or not result.ok:
            failures += 1
    mem_end = _mem_free()
    if mem_end is not None:
        _log("PROOF:MARKER", "mem_free_end=%d" % mem_end)
    # Lock iterations gate PASS; memory markers are observational when available.
    ok = failures == 0
    detail = "failures=%d" % failures
    if mem_start is not None and mem_end is not None:
        detail += " mem_free_start=%d mem_free_end=%d" % (mem_start, mem_end)
    _marker(name, "PASS" if ok else "FAIL", detail)
    return ok


def _settle(mailbox, lock, worker, timeout_ms=None):
    """Wait for idle + drain, or soft_reset, before the next scenario."""
    if timeout_ms is None:
        timeout_ms = config.PROOF_BUSY_OP_MS + 2000
    deadline = ticks.ticks_add(ticks.ticks_ms(), timeout_ms)
    while ticks.ticks_diff(deadline, ticks.ticks_ms()) > 0:
        idle, has_cmd, has_res = _with_lock(
            lock,
            lambda: (mailbox.idle, mailbox.has_command, mailbox.has_result),
        )
        if has_res:
            _take_result(mailbox, lock)
            continue
        if idle and not has_cmd:
            worker.fatal = None
            return
        _sleep_ms(20)
    _with_lock(lock, mailbox.soft_reset)
    worker.fatal = None


def run_proof():
    """
    Run the full Story 1.4 device proof checklist with serial markers.

    Intended for gated flash via ``config.NETWORK_PROOF_MODE``. Does not wire
    production App NTP integration.
    """
    _log("PROOF:SUITE_BEGIN", "story-1-4-network-mailbox")
    mailbox = Mailbox()
    lock = _allocate_lock()
    ops = StubOps(mode="success", delay_ms=0)
    worker = NetworkWorker(mailbox, lock, ops, log=_log)
    worker.start()
    _sleep_ms(50)

    scenarios = (
        ("success_dns_ntp", scenario_success_dns_ntp),
        ("fail_dns", scenario_fail_dns),
        ("fail_ntp", scenario_fail_ntp),
        ("result_slot_contention", scenario_result_contention),
        ("stale_expired_results", scenario_stale_expired),
        ("retry_sequencing", scenario_retry_sequencing),
        ("soft_reset", scenario_soft_reset),
        ("render_continuity", scenario_render_continuity),
        ("sustained_lock_memory", scenario_sustained_lock),
    )
    results = []
    for name, fn in scenarios:
        ok = fn(mailbox, lock, worker, ops)
        results.append((name, ok))
        _settle(mailbox, lock, worker)

    worker.stop()
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    _log("PROOF:SUITE_SUMMARY", "passed=%d total=%d" % (passed, total))
    for name, ok in results:
        _log("PROOF:SUITE_ROW", name, "PASS" if ok else "FAIL")
    _log("PROOF:SUITE_END", "story-1-4-network-mailbox")
    # Keep process alive so serial capture is not truncated by immediate reset.
    while True:
        _sleep_ms(60_000)
