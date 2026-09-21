---
title: 'Add an alert with a time and recurrence'
type: 'feature'
created: '2026-09-21'
status: 'done'
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

- `src/device/web/page_settings_content.py`, `src/device/web/page_alert_editor.py` -- flat Config alert list, Add link/editor, weekday labels, feedback, and limit state; editor remains lazy for heap headroom.
- `src/device/web/router.py`, `src/device/web/settings_post.py` -- authenticated GET/POST routing; password flow retained and Add flow kept lazy.
- `src/device/web/alert_validation.py`, `src/device/web/alert_route.py` -- pure form validation and atomic SettingsStore append path, loaded only for Add requests.
- `src/device/web/pages.py` -- carries alert editor, success, and error state through response builders.
- `tests/test_provisioning_validation.py`, `tests/test_config_auth.py` -- validation, atomic persistence, auth, rendering, limit, and no-op failure evidence.

## Tasks & Acceptance

**Execution:**
- `src/device/web/alert_validation.py`, `src/device/web/alert_route.py` -- validate form and append through existing SettingsStore atomic commit -- prevent malformed records entering persistence.
- `src/device/web/page_settings_content.py`, `src/device/web/page_alert_editor.py`, `src/device/web/pages.py` -- render Add/editor/weekday controls and bounded feedback -- satisfy browser UX without increasing initial station heap.
- `src/device/web/router.py`, `src/device/web/settings_post.py` -- route authenticated Add and preserve password-change KDF path -- apply immediately without reboot.
- `tests/test_provisioning_validation.py`, `tests/test_config_auth.py` -- test matrix and persistence/auth boundaries -- prove no-op invalid paths.

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

## Review Triage Log

### 2026-09-21 — Review pass
- verdicts: 0 findings — high 0, medium 0, low 0, false 0, maybe-false 0
- findings:
  - Manual review completed because invocation explicitly prohibited reviewer-agent spawning; no actionable findings.

## Auto Run Result

Status: done

Summary: Added authenticated Add alert flow with lazy form validation/persistence modules, inline time/enabled/weekday editor, one-time and weekday recurrence handling, success/error feedback, ten-alert protection, and atomic SettingsStore commits. Preserved password-change behavior and reduced station-web footprint to satisfy heap gates.

Files changed:
- `src/device/web/alert_validation.py`, `src/device/web/alert_route.py`, `src/device/web/settings_post.py` -- lazy validation, atomic Add persistence, and authenticated POST handling.
- `src/device/web/page_alert_editor.py`, `src/device/web/page_settings_content.py`, `src/device/web/pages.py` -- Config Add/editor/list/feedback rendering.
- `src/device/web/router.py` -- authenticated Add route and `/settings/add` editor route.
- `tests/test_config_auth.py`, `tests/test_provisioning_validation.py` -- Story 1.2 acceptance and edge-case coverage.
- `_bmad-output/implementation-artifacts/alert-clock/epic-1-context.md`, this story artifact, sprint status, and graphify output -- implementation trail and generated graph refresh.

Review findings breakdown: 0 patches, 0 deferred items, 0 rejected findings. Manual review used because agent spawning was explicitly prohibited.

Follow-up review recommendation: false.

Verification:
- `uv run pytest tests/test_provisioning_validation.py tests/test_settings_store.py tests/test_config_auth.py` -- 65 passed.
- `uv run pytest` -- 576 passed.
- Hostsim size/heap checks -- boot 46,825 bytes, station web 35,382 bytes, combined 82,207 bytes; all contiguous probes passed.
- `git diff --check` -- passed.

Residual risks: Pico browser/device behavior and restart persistence remain unverified on hardware; no on-device claim made.
