---
title: 'Alert Toggle Button Ignores Touch'
type: 'bugfix'
created: '2026-10-10'
baseline_revision: 'c01e418a94fae7ac93e1f389dcf55f8cad6b921f'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Touching an alert's ON/OFF control appears to do nothing, preventing users from changing saved alert state from the clock.

**Approach:** Make visible alert state controls reliably respond to calibrated touch and give immediate visual feedback for both successful and failed commits. Preserve state unless persistence succeeds.

## Boundaries & Constraints

**Always:** Keep 320×240 layout, five rows per page, visible 80×30 state controls, recurrence display, paging, and 60-second idle timeout. Use existing calibrated touch coordinates and settings-store authority. A successful touch changes only selected alert; failed persistence retains previous state and keeps Alerts usable.

**Never:** Change hardware pins/calibration without device evidence; alter alert scheduling, recurrence, active-alert behavior, web administration, or settings schema.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| Toggle control | Touch visible ON/OFF control | One alert value persists, state redraws, timeout renews | No error expected |
| Touch near visible control | Calibrated touch lands near control edge | Intended row responds reliably without selecting another alert | Outside control remains ordinary dismissal |
| Commit failure | Store rejects changed settings | Previous state remains and visible failure feedback appears; Alerts stays open | Keep secret-free diagnostic |

</intent-contract>

## Code Map

- `src/ui/alert_list_view.py` -- `state_rect`, `state_index`, and `handle_touch` define control geometry and row selection; widen forgiving hit area while keeping visual control geometry clear.
- `src/ui/tap.py` -- routes touch edges to alert-list handling and reports control presses to App timeout logic.
- `src/app.py` -- `_poll_touch` preserves Alerts surface and renews timeout for controls; active-alert path has precedence.
- `src/alert/runtime.py` -- `toggle_enabled` commits copied settings and emits secret-free persistence failures; retain commit authority and prior-state guarantee.
- `src/ui/alerts.py` -- cached render key follows alert values; ensure press/failure feedback invalidates or redraws view.
- `src/device/touch_port.py`, `src/ui/touch_calibration.py`, `src/config.py` -- touch samples are debounced and calibrated to screen coordinates; inspect mapping without changing physical calibration absent device evidence.

## Tasks & Acceptance

**Execution:**
- `src/ui/alert_list_view.py` -- make touch selection tolerant around the visible control while preventing adjacent-row selection -- physical taps reliably target intended alert.
- `src/ui/alert_list_view.py`, `src/ui/alerts.py` -- show prompt control feedback and clear it after outcome -- user sees touch and commit result.
- `src/app.py` and `src/alert/runtime.py` -- preserve single-toggle commit semantics and recoverable failure state -- no optimistic persistence mutation.

**Acceptance Criteria:**
- Given Alerts list open, when user taps visible ON/OFF control, then selected alert changes once, persists, redraws, and idle deadline renews.
- Given touch lands at edge of visible control, when it remains within that control's forgiving target, then only intended row toggles.
- Given persistence fails, when user taps a control, then saved/displayed value stays unchanged, failure feedback appears, and next tap remains usable.
- Given active alert owns display, when user touches screen, then existing active-alert behavior consumes touch.

## Review Triage Log

### 2026-10-10 — Review pass
- verdicts: 12 findings — high 0, medium 0, low 10, false 2, maybe-false 0
- findings:
  - `[low]` `[patch]` Feedback used row index — changed to alert ID; renderer now follows the same alert if list order changes.
  - `[low]` `[patch]` Paging retained short-lived feedback — page changes now clear feedback and its deadline.
  - `[low]` `[patch]` Feedback expiry lacked a test — integration test checks scheduled redraw, expiry, and return to normal control color.
  - `[low]` `[patch]` Failed-save test did not prove unchanged displayed state — test now checks failure highlight, post-failure OFF redraw, and unchanged store record.
  - `[low]` `[patch]` Missing-alert diagnostic lacked direct coverage — stale-ID test now checks secret-free code and unchanged saved record.
  - `[low]` `[patch]` Row-edge coverage was incomplete — tests exercise top and bottom coordinates for all five visible rows and adjacent-row boundaries.
  - `[low]` `[patch]` Outside-tap dismissal lacked integration coverage — App test taps outside control and verifies return to rotation.
  - `[low]` `[patch]` Successful visual feedback lacked coverage — App test checks success flash and new ON label.
  - `[false]` `[reject]` Unexpected commit errors use overly generic diagnostic — `toggle_enabled` preserves an exception's bounded `.code` and otherwise emits secret-free `commit`; generic fallback is intentional and cannot reveal exception contents.
  - `[low]` `[patch]` Auto Run Result and frontmatter status conflicted — result and final frontmatter now both report `done`.
  - `[low]` `[patch]` Feedback expiry lacked independent verification — same expiry integration test proves deadline wakeup and clearing; this duplicates the blind-hunter coverage gap.
  - `[false]` `[reject]` Report might refer to web/admin or another alert surface — invocation says touch, and active alert-clock artifacts define the ON/OFF Alerts-list control; code and tests match that surface.

## Design Notes

Touch handler currently uses the same 80×30 rectangle as the painted control and returns a handled press even when persistence fails. Alerts renderer caches by alert data and page, so feedback needs explicit invalidation or an included transient state.

## Verification

**Commands:**
- `uv run pytest tests/test_alert_app.py tests/test_alert_list_view.py tests/test_touch_calibration.py tests/test_touch_state.py` -- expected: all focused touch, toggle, persistence, and routing tests pass.
- `git diff --check` -- expected: no whitespace errors.

**Manual checks (device):**
- Flash Pico W; tap center and edges of ON/OFF controls on first and second pages; confirm intended alert changes once and persists after reopening/reboot.
- Force or simulate a store failure; confirm visible feedback, unchanged state, and successful later retry. Host checks cannot prove physical calibration or display behavior.


## Auto Run Result

Status: done

Summary: Alert-list controls now accept the whole row and a small horizontal margin around the painted button. Successful and failed commits show brief feedback; feedback follows alert ID across reordering and clears on paging or timeout. Missing alerts log a secret-free diagnostic. Failed commits retain saved and displayed state.

Files changed:
- `src/ui/alert_list_view.py` -- forgiving row hit target, ID-bound feedback, paging cleanup.
- `src/ui/alerts.py` -- include feedback in render cache and clear it at expiry.
- `src/ui/tap.py` -- pass touch timestamp into alert handler.
- `src/app.py` -- schedule a redraw for transient feedback expiry.
- `src/alert/runtime.py` -- log missing selected alert.
- `tests/test_alert_app.py` -- cover saved toggles, success/failure feedback, expiry, missing IDs, and outside dismissal.
- `tests/test_alert_list_view.py` -- cover row boundaries, page clearing, and feedback following ID after reorder.
- `graphify-out/` -- refresh root code graph.
- `_bmad-output/implementation-artifacts/alert-clock/spec-alert-toggle-button-ignores-touch.md` -- record scope, implementation, review, and verification.

Review findings: 10 low findings patched; 0 deferred; 2 false findings rejected with evidence in Review Triage Log. Patched counts: high 0, medium 0, low 10. Follow-up review recommendation: false.

Verification: `uv run pytest tests/test_alert_app.py tests/test_alert_list_view.py tests/test_touch_calibration.py tests/test_touch_state.py` passed (60 tests). `git diff --check` passed. `graphify update .` completed. Pico W physical touch, display, and reboot-persistence checks remain unverified; host tests cannot measure actual calibrated tap coordinates.
