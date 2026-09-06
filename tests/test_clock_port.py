"""Host tests for RtcClockPort with a stubbed machine.RTC."""

from __future__ import annotations

import importlib
import sys
import types

from src.time.model import DateTime


def _install_fake_machine():
    machine = types.ModuleType("machine")

    class FakeRTC:
        def __init__(self, parts=None):
            self._parts = parts

        def datetime(self, value=None):
            if value is not None:
                self._parts = value
                return None
            return self._parts

    machine.RTC = FakeRTC
    sys.modules["machine"] = machine
    return FakeRTC


def _load_clock_port():
    sys.modules.pop("src.device.clock_port", None)
    return importlib.import_module("src.device.clock_port")


def _cleanup_device_stub():
    sys.modules.pop("src.device.clock_port", None)
    sys.modules.pop("machine", None)


def test_cold_and_invalid_rtc_map_to_none():
    FakeRTC = _install_fake_machine()
    try:
        clock_port = _load_clock_port()
        cases = [
            None,
            (2000, 1, 1, 5, 0, 0, 0, 0),  # classic unset
            (2021, 1, 1, 4, 0, 0, 0, 0),  # common power-on year
            (2023, 6, 15, 3, 12, 0, 0, 0),  # below floor 2024
            (2026, 2, 30, 0, 12, 0, 0, 0),  # day outside February
            (2026, 4, 31, 4, 12, 0, 0, 0),  # day 31 in 30-day month
            (2026, 13, 1, 0, 0, 0, 0, 0),  # bad month
        ]
        for parts in cases:
            port = clock_port.RtcClockPort(rtc=FakeRTC(parts))
            assert port.read_utc() is None, parts
    finally:
        _cleanup_device_stub()


def test_valid_rtc_tuple_maps_to_datetime():
    FakeRTC = _install_fake_machine()
    try:
        clock_port = _load_clock_port()
        parts = (2026, 9, 6, 6, 7, 30, 15, 0)
        port = clock_port.RtcClockPort(rtc=FakeRTC(parts))
        assert port.read_utc() == DateTime(2026, 9, 6, 6, 7, 30, 15)
    finally:
        _cleanup_device_stub()


def test_set_utc_writes_rtc_tuple():
    FakeRTC = _install_fake_machine()
    try:
        clock_port = _load_clock_port()
        rtc = FakeRTC(None)
        port = clock_port.RtcClockPort(rtc=rtc)
        port.set_utc(DateTime(2026, 9, 6, 6, 8, 0, 0))
        assert rtc._parts == (2026, 9, 6, 6, 8, 0, 0, 0)
    finally:
        _cleanup_device_stub()
