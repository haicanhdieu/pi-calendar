"""Host coverage for the reset device boundary."""

from src.device.reboot_port import RebootPort


def test_reset_invokes_injected_callback_once():
    calls = []
    port = RebootPort(lambda: calls.append("reset"))

    assert port.reset() is None
    assert calls == ["reset"]
