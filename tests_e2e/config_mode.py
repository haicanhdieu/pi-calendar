"""Shared E2E helper: put the device into config mode before testing it.

Since issue #2 the device boots into one of two modes. Clock mode runs no web
stack at all -- its only HTTP presence is a knock listener that answers any
connection with a fixed interstitial, writes a flag and resets into config
mode, where the admin site is served with the heap to itself.

So the first request of a test run may legitimately be answered by the
interstitial rather than by the site. This helper performs that knock and
waits for the device to come back up serving the real login page.
"""

import time

import requests

# A reset plus Wi-Fi association; measured at roughly 8 seconds on the bench
# unit, with headroom for a slow DHCP lease.
CONFIG_MODE_BOOT_TIMEOUT_S = 45
_POLL_INTERVAL_S = 2
_INTERSTITIAL_MARKER = "Entering config mode"


class DeviceUnreachable(Exception):
    """The device answered neither the admin site nor the knock listener."""


def _get_login(base_url, timeout):
    return requests.get(base_url + "/login", timeout=timeout)


def ensure_config_mode(base_url, timeout=8, boot_timeout=CONFIG_MODE_BOOT_TIMEOUT_S):
    """Return once the device is serving the admin site.

    Knocks if the device is in clock mode, then polls until the login page
    comes back. Raises :class:`DeviceUnreachable` if it never does.
    """
    base_url = base_url.rstrip("/")
    deadline = time.time() + boot_timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = _get_login(base_url, timeout)
        except requests.exceptions.RequestException as exc:
            # Expected while the device is mid-reset.
            last_error = exc
            time.sleep(_POLL_INTERVAL_S)
            continue
        if response.status_code == 200 and _INTERSTITIAL_MARKER not in response.text:
            return response
        # Either the knock interstitial (the device is now rebooting) or a
        # transient failure; both are resolved by waiting.
        last_error = "status={} interstitial={}".format(
            response.status_code, _INTERSTITIAL_MARKER in response.text
        )
        time.sleep(_POLL_INTERVAL_S)
    raise DeviceUnreachable(
        "device at {} never reached config mode within {}s (last: {})".format(
            base_url, boot_timeout, last_error
        )
    )
