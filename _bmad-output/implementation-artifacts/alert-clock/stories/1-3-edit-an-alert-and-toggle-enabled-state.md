---
title: 'Edit an alert and toggle its enabled state'
type: 'feature'
created: '2026-09-21'
status: 'done'
baseline_revision: '06120d0b9b88c75fabd0200130c489584da49d22'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/implementation-artifacts/alert-clock/epic-1-context.md
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Authenticated Config can add and list alerts but cannot adjust an existing schedule or switch an alert on or off.

**Approach:** Extend the existing inline alert editor and authenticated mutation path to load one selected alert, validate a complete replacement record, preserve its stable id, and atomically commit the updated alert list.

## Boundaries & Constraints

**Always:** Keep one inline editor open at a time; prefill current time, enabled state, and weekdays; preserve alert id and unrelated alerts; treat empty weekdays as one-time; validate before commit; preserve Wi-Fi/admin/postpone fields; keep pure validation hardware-free; require an authenticated session.

**Never:** Implement delete behavior, postpone-delay mutation, scheduling, TFT, buzzer, new pages, or unauthenticated mutation. Delete remains disabled editor affordance for Story 1.4.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Edit time | Authenticated editor for existing id, 07:00 → 06:30 | Same id, recurrence, and enabled state; only time changes and persists | No error |
| Edit recurrence | Existing weekdays Monday–Friday, all weekday fields cleared | Stored weekdays become `[]`; row says `One time` | No error |
| Toggle disabled | Existing enabled alert, checkbox cleared | Stored `enabled` becomes false; time and recurrence remain | No error |
| Invalid edit | Missing/invalid time, malformed weekday, unknown id, or tampered fields | No commit; bounded inline error; prior record unchanged | Return settings page with 400 status |

</intent-contract>

## Code Map

- `src/device/web/page_settings_content.py` -- render each row and selected row's inline editor; preserve flat Config layout and one-editor behavior.
- `src/device/web/page_alert_editor.py` -- render add/edit form fields with escaped current values and weekday selections.
- `src/device/web/alert_validation.py` -- validate shared alert form fields and distinguish add versus edit without hardware imports.
- `src/device/web/alert_route.py` -- locate existing id, replace exactly one alert, and commit complete settings atomically.
- `src/device/web/settings_post.py`, `src/device/web/router.py`, `src/device/web/pages.py` -- route authenticated edit GET/POST and carry editor/error state.
- `tests/test_config_auth.py`, `tests/test_provisioning_validation.py` -- prove edit, recurrence, toggle, auth, invalid no-op, and persistence boundaries.

## Tasks & Acceptance

**Execution:**
- `src/device/web/page_alert_editor.py`, `src/device/web/page_settings_content.py` -- render selected alert editor prefilled in place and leave other rows collapsed -- satisfy browser interaction contract.
- `src/device/web/alert_validation.py`, `src/device/web/alert_route.py` -- validate edit action and replace only matching id through SettingsStore -- preserve atomicity and unrelated data.
- `src/device/web/router.py`, `src/device/web/settings_post.py`, `src/device/web/pages.py` -- authenticate edit routes and return bounded success/error pages -- prevent unauthenticated mutation.
- `tests/test_provisioning_validation.py`, `tests/test_config_auth.py` -- cover valid edits, one-time conversion, disabled state, invalid no-op, unknown id, and restart-loaded values -- prove acceptance matrix.

**Acceptance Criteria:**
- Given an authenticated Config page listing alerts, when one row is opened, then only that row expands inline with current time, enabled state, and weekday selection prefilled.
- Given an open editor, when 07:00 changes to 06:30 and saves, then the existing id and all other fields remain unchanged except time, and the list shows 06:30.
- Given Monday–Friday recurrence, when all weekdays are cleared and saved, then the stored recurrence is empty and the list says `One time`.
- Given an enabled alert, when enabled is cleared and saved, then it remains stored with `enabled: false`, original time and recurrence, and visible disabled state.
- Given invalid or tampered edit input, when Save is submitted, then inline feedback appears and the persisted record is byte-for-byte unchanged.

## Verification

**Commands:**
- `uv run pytest tests/test_provisioning_validation.py tests/test_settings_store.py tests/test_config_auth.py` -- expected: all focused tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.
- `graphify update .` -- expected: graphify output reflects changed source and tests.

## Review Triage Log

### 2026-09-21 — Review pass
- verdicts: 0 findings — high 0, medium 0, low 0, false 0, maybe-false 0
- findings:
  - Manual review completed; no actionable findings. Reviewer subagent layers unavailable in this runtime.

## Auto Run Result

Status: done

Summary: Added authenticated inline alert editing with prefilled time, enabled state, and weekday recurrence. Edit saves preserve stable alert ids and unrelated settings, support one-time recurrence, toggle enabled state, and reject invalid or unknown edits without mutation.

Files changed:
- `src/device/web/alert_validation.py` -- validate edit actions and matching alert ids.
- `src/device/web/alert_route.py` -- atomically replace one existing alert.
- `src/device/web/page_alert_editor.py`, `src/device/web/page_settings_content.py` -- render prefilled inline editors and edit links.
- `src/device/web/router.py`, `src/device/web/settings_post.py`, `src/device/web/pages.py` -- authenticate and route edit GET/POST flows.
- `tests/test_provisioning_validation.py`, `tests/test_config_auth.py` -- cover edit validation, time/recurrence/toggle changes, invalid no-op, unknown id, and persistence.
- `graphify-out/` -- refreshed generated graph output.
- `1-3-edit-an-alert-and-toggle-enabled-state.md` -- implementation artifact and status.

Review findings breakdown: 0 patches applied, 0 items deferred, 0 rejected findings. Manual review used because reviewer subagent layers were unavailable.

Follow-up review recommendation: false.

Verification:
- Focused tests: 68 passed.
- Full host suite: 579 passed.
- `git diff --check`: passed.
- `graphify update .`: passed.

Residual risks: Pico browser behavior, restart persistence on hardware, and device heap behavior require flashing and on-device validation; no device behavior claimed.
