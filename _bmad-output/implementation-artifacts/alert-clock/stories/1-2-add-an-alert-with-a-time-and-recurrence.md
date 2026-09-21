---
title: 'Add an alert with a time and recurrence'
type: 'feature'
created: '2026-09-21'
status: 'in-review'
baseline_revision: '17560d6ba0243eab68de8a720f366e00276099bc'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/implementation-artifacts/alert-clock/epic-1-context.md
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Authenticated Config can display stored alerts but cannot create one, so the device cannot be configured for a new wake time.

**Approach:** Add an inline authenticated form that validates local time, enabled state, and multi-select weekday recurrence, then appends one canonical alert through SettingsStore's atomic version-2 commit.

## Boundaries & Constraints

**Always:** Preserve existing settings; use stable lowercase alert ids; map Monday to index 0; empty weekdays means one-time; enforce max ten alerts; escape browser output; keep pure validation hardware-free; show bounded success/error feedback.

**Never:** Implement edit/delete behavior, postpone-delay mutation, scheduling, TFT, buzzer, new pages, or unauthenticated alert mutation. Delete control may be present as editor affordance required by UX, but must not remove data in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid add | Authenticated session, fewer than ten alerts, 07:00, enabled, weekdays 0–4 | One canonical alert appended and atomically persisted; success feedback and readable row appear | No error |
| One-time add | Authenticated session, empty weekday selection | Alert persists with `weekdays: []`; row says `One time` | No error |
| Invalid form | Missing time, invalid hour/minute, malformed/duplicate/out-of-range weekday values, or invalid enabled field | No commit; existing record unchanged; inline danger feedback names invalid field | Return bounded bad request/page |
| Limit | Ten stored alerts | Add unavailable with clear ten-alert explanation; request cannot commit eleventh alert | Reject without mutation |
| Auth boundary | Missing/expired session | Existing redirect/session behavior; no alert values or mutation | Reject before settings mutation |

</intent-contract>

## Code Map

- `src/provisioning/validation.py` -- canonical v2 record rules; add focused alert/form validation while retaining whole-record validation.
- `src/device/settings_store.py` -- atomic `commit()` boundary; pass existing Wi-Fi/admin values and current alert list.
- `src/device/web/page_settings_content.py` -- flat Config alert section, Add control, inline editor, weekday labels, feedback, limit state.
- `src/device/web/router.py` -- authenticated POST routing and form parsing; reject invalid add requests before coordinator commit.
- `src/device/web/server.py` -- dispatch new bounded authenticated add action through cooperative HTTP.
- `src/device/network/coordinator.py` -- commit validated alert against current canonical settings and return rendered page.
- `tests/test_provisioning_validation.py`, `tests/test_settings_store.py`, `tests/test_config_auth.py` -- validation, atomic persistence, auth, rendering, limit, and no-op failure evidence.

## Tasks & Acceptance

**Execution:**
- `src/provisioning/validation.py` -- validate add form and canonical alert fields -- prevent malformed records entering atomic commit.
- `src/device/web/page_settings_content.py` -- render Add/editor/weekday controls and bounded feedback -- satisfy browser UX.
- `src/device/web/router.py`, `src/device/web/server.py`, `src/device/network/coordinator.py` -- route authenticated add and commit one updated record -- apply immediately without reboot.
- `tests/test_provisioning_validation.py`, `tests/test_settings_store.py`, `tests/test_config_auth.py` -- test matrix and persistence/auth boundaries -- prove no-op invalid paths.

**Acceptance Criteria:**
- Given an authenticated Config page with fewer than ten alerts, when Add alert is activated, then an inline editor offers time, enabled, seven text weekday controls, Save, and Delete, with no label/sound/volume/per-alert postpone controls.
- Given the editor, when no weekday is selected, then saved alert recurrence is one-time; when any subset is selected, then saved weekdays use Monday index 0 and render readably.
- Given valid 07:00, enabled, Monday–Friday, when Save is submitted, then one stable lowercase-id alert is appended, the full record is validated and atomically committed, success feedback appears, and the row is visible without reboot.
- Given missing, invalid, or malformed form fields, when Save is submitted, then danger feedback appears and stored settings remain byte-for-byte unchanged.
- Given ten stored alerts, when Config loads or an add request arrives, then Add is unavailable with explanation and no eleventh alert can be committed.
- Given a saved alert, when the Device restarts, then time, enabled state, and recurrence remain intact with Wi-Fi/admin settings preserved.

## Verification

**Commands:**
- `uv run pytest tests/test_provisioning_validation.py tests/test_settings_store.py tests/test_config_auth.py` -- expected: all focused tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.
