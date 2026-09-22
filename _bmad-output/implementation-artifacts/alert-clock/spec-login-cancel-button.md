---
title: 'Add cancel button to settings login page'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The settings login page gives users no way to abandon config mode before authenticating, leaving the Pi in settings mode until timeout.

**Approach:** Add a visible Cancel button linking to the existing config exit route. Allow that exit route without a session so unauthenticated users can return to clock mode.

</frozen-after-approval>

## Implementation Notes

- Added Cancel control to `src/device/web/page_login_content.py`, targeting existing `/exit` route.
- Made `GET /exit` public in `src/device/web/router.py`; it remains limited to `STATION_ONLINE` and only requests the existing reset-to-clock flow.
- Updated `tests/test_config_auth.py` for login-page markup and unauthenticated exit behavior.
- Verified `uv run pytest -q`: 673 passed.

## Review Triage Log

- No findings from direct diff and route review. Blind-hunter subagent skipped because no subagent tool was available.
