"""Host tests for the pure AD-8 capacity-one mailbox protocol."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from src import ticks
from src.device.network.mailbox import (
    Mailbox,
    MailboxSaturationError,
    SyncCommand,
    SyncResult,
    result_is_expired,
    should_apply_result,
)
from src.time.model import DateTime

ROOT = Path(__file__).resolve().parents[1]
MAILBOX_PATH = ROOT / "src" / "device" / "network" / "mailbox.py"
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "_thread"}
)


def _remember_module(roots: set[str], name: str) -> None:
    if not name:
        return
    parts = name.split(".")
    for i in range(len(parts)):
        roots.add(".".join(parts[: i + 1]))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _remember_module(roots, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _remember_module(roots, node.module)
            for alias in node.names:
                _remember_module(roots, f"{node.module}.{alias.name}")
    return roots


def _sample_utc():
    return DateTime(2026, 9, 6, 6, 12, 0, 0)


class _FakeLock:
    def acquire(self):
        return True

    def release(self):
        return None


def test_mailbox_module_imports_under_cpython():
    from src.device.network.mailbox import Mailbox as M

    assert M().idle is True


def test_mailbox_ast_bans_device_and_thread_apis():
    roots = _imported_roots(MAILBOX_PATH)
    forbidden = roots & FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"mailbox.py imports forbidden modules: {forbidden}"


def test_package_init_exports_mailbox_only_surface():
    import src.device.network as network_pkg

    assert hasattr(network_pkg, "Mailbox")
    assert hasattr(network_pkg, "SyncCommand")
    assert hasattr(network_pkg, "SyncResult")
    # Worker/proof must not be pulled in by package import.
    assert "src.device.network.worker" not in sys.modules
    assert "src.device.network.proof" not in sys.modules


def test_enqueue_while_idle_accepts_and_marks_busy():
    box = Mailbox()
    cmd = SyncCommand(1, 1000)
    assert box.enqueue(cmd) is True
    assert box.idle is False
    assert box.has_command is True


def test_enqueue_while_busy_rejects_without_overwrite():
    box = Mailbox()
    first = SyncCommand(1, 1000)
    second = SyncCommand(2, 2000)
    assert box.enqueue(first) is True
    assert box.enqueue(second) is False
    taken = box.try_take_command()
    assert taken[0] == first


def test_enqueue_rejected_when_not_idle_even_if_command_slot_empty():
    box = Mailbox()
    assert box.enqueue(SyncCommand(1, 1000)) is True
    cmd, _epoch = box.try_take_command()
    assert cmd == SyncCommand(1, 1000)
    assert box.has_command is False
    assert box.idle is False
    assert box.enqueue(SyncCommand(2, 2000)) is False


def test_consume_and_publish_terminal_result():
    box = Mailbox()
    box.enqueue(SyncCommand(3, 5000))
    cmd, epoch = box.try_take_command()
    assert cmd.command_id == 3
    result = SyncResult(3, True, _sample_utc(), None)
    assert box.publish_result(result, epoch) is True
    assert box.idle is True
    assert box.try_take_result() == result
    assert box.has_result is False


def test_publish_failure_result_with_error_code():
    box = Mailbox()
    box.enqueue(SyncCommand(4, 5000))
    _cmd, epoch = box.try_take_command()
    result = SyncResult(4, False, None, "dns_fail")
    box.publish_result(result, epoch)
    taken = box.try_take_result()
    assert taken.ok is False
    assert taken.error_code == "dns_fail"
    assert taken.utc is None


def test_result_saturation_raises_and_leaves_prior_untouched():
    box = Mailbox()
    box.enqueue(SyncCommand(5, 5000))
    _cmd, epoch = box.try_take_command()
    first = SyncResult(5, True, _sample_utc(), None)
    box.publish_result(first, epoch)
    with pytest.raises(MailboxSaturationError):
        box.publish_result(SyncResult(6, False, None, "ntp_fail"), epoch)
    assert box.try_take_result() == first


def test_matching_fresh_result_is_accepted():
    now = 10_000
    deadline = ticks.ticks_add(now, 5_000)
    result = SyncResult(7, True, _sample_utc(), None)
    assert should_apply_result(result, 7, deadline, now) is True
    assert result_is_expired(deadline, now) is False


def test_stale_mismatch_and_expired_results_are_discarded():
    now = 10_000
    deadline = ticks.ticks_add(now, 5_000)
    mismatch = SyncResult(99, True, _sample_utc(), None)
    assert should_apply_result(mismatch, 7, deadline, now) is False

    expired_deadline = ticks.ticks_add(now, -1)
    fresh_id = SyncResult(7, True, _sample_utc(), None)
    assert should_apply_result(fresh_id, 7, expired_deadline, now) is False
    assert result_is_expired(expired_deadline, now) is True


def test_retry_sequencing_requires_consume_and_idle():
    box = Mailbox()
    assert box.enqueue(SyncCommand(8, 1000)) is True
    assert box.enqueue(SyncCommand(9, 2000)) is False  # busy / in-flight
    _cmd, epoch = box.try_take_command()
    assert box.enqueue(SyncCommand(9, 2000)) is False  # still not idle
    box.publish_result(SyncResult(8, False, None, "ntp_fail"), epoch)
    assert box.idle is True
    assert box.has_result is True
    # Prior result unconsumed → retry enqueue blocked by protocol.
    assert box.enqueue(SyncCommand(9, 2000)) is False
    prior = box.try_take_result()
    assert prior.command_id == 8
    assert box.enqueue(SyncCommand(9, 2000)) is True
    _cmd2, epoch2 = box.try_take_command()
    box.publish_result(SyncResult(9, True, _sample_utc(), None), epoch2)
    assert box.try_take_result().command_id == 9


def test_retry_allowed_only_after_consume_and_idle():
    box = Mailbox()
    box.enqueue(SyncCommand(10, 1000))
    _cmd, epoch = box.try_take_command()
    box.publish_result(SyncResult(10, True, _sample_utc(), None), epoch)
    assert box.idle is True
    assert box.has_result is True
    assert box.enqueue(SyncCommand(11, 2000)) is False
    assert box.try_take_result() is not None
    assert box.has_result is False
    assert box.enqueue(SyncCommand(11, 2000)) is True


def test_soft_reset_after_publish_clears_and_allows_enqueue():
    box = Mailbox()
    box.enqueue(SyncCommand(12, 1000))
    _cmd, epoch = box.try_take_command()
    box.publish_result(SyncResult(12, False, None, "planted"), epoch)
    box.soft_reset()
    assert box.idle is True
    assert box.has_command is False
    assert box.has_result is False
    assert box.enqueue(SyncCommand(13, 2000)) is True


def test_soft_reset_after_take_without_publish():
    box = Mailbox()
    box.enqueue(SyncCommand(20, 1000))
    box.try_take_command()
    assert box.idle is False
    box.soft_reset()
    assert box.idle is True
    assert box.has_command is False
    assert box.has_result is False
    assert box.enqueue(SyncCommand(21, 2000)) is True


def test_soft_reset_after_enqueue_without_take():
    box = Mailbox()
    box.enqueue(SyncCommand(22, 1000))
    assert box.has_command is True
    box.soft_reset()
    assert box.idle is True
    assert box.has_command is False
    assert box.has_result is False
    assert box.enqueue(SyncCommand(23, 2000)) is True


def test_soft_reset_epoch_discards_orphan_publish():
    box = Mailbox()
    box.enqueue(SyncCommand(30, 1000))
    _cmd, take_epoch = box.try_take_command()
    box.soft_reset()
    assert take_epoch != box.epoch
    assert (
        box.publish_result(SyncResult(30, True, _sample_utc(), None), take_epoch)
        is False
    )
    assert box.has_result is False
    assert box.idle is True
    assert box.enqueue(SyncCommand(31, 2000)) is True


def test_occupy_result_keeps_busy_for_contention_plant():
    box = Mailbox()
    box.enqueue(SyncCommand(40, 1000))
    box.try_take_command()
    assert box.idle is False
    box.occupy_result(SyncResult(90, False, None, "planted"))
    assert box.idle is False
    assert box.has_result is True


def test_try_take_empty_slots_return_none():
    box = Mailbox()
    assert box.try_take_command() is None
    assert box.try_take_result() is None


def test_worker_publish_saturation_sets_fatal_and_preserves_prior():
    from src.device.network.worker import NetworkWorker

    box = Mailbox()
    lock = _FakeLock()
    worker = NetworkWorker(box, lock, ops=None, log=lambda *a: None)
    box.enqueue(SyncCommand(50, 60_000))
    _cmd, epoch = box.try_take_command()
    prior = SyncResult(50, False, None, "planted")
    box.occupy_result(prior)
    worker._publish(SyncResult(50, True, _sample_utc(), None), epoch)
    assert worker.fatal is not None
    assert box.try_take_result() == prior


def test_worker_deadline_before_ops_returns_deadline_error():
    from src.device.network.worker import NetworkWorker

    class _Ops:
        def run(self, command):
            raise AssertionError("ops must not run after deadline")

    box = Mailbox()
    lock = _FakeLock()
    worker = NetworkWorker(box, lock, ops=_Ops(), log=lambda *a: None)
    past = ticks.ticks_add(ticks.ticks_ms(), -1)
    result = worker._run_ops(SyncCommand(60, past))
    assert result.ok is False
    assert result.error_code == "deadline"
