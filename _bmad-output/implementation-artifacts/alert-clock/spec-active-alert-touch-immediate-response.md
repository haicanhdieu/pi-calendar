---
title: 'Stop active-alert ringing immediately on touch'
type: bugfix
created: '2026-09-23'
status: done
baseline_commit: '7419d8e2443800490a51647a2f636a138df115d4'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - _bmad-output/planning-artifacts/alert-clock/prds/prd.md
  - _bmad-output/planning-artifacts/alert-clock/architecture/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md
warnings: []
deferred: []
baseline_revision: '7419d8e2443800490a51647a2f636a138df115d4'
---

<intent-contract>

## Intent

**Problem:** Tapping STOP or POSTPONE on the active-alert screen does not reliably silence the buzzer immediately. The alert can continue ringing for seconds, forcing repeated or prolonged touches and leaving the owner unsure whether the action registered.

**Approach:** Make the first valid touch inside either visible active-alert action target resolve in the same cooperative loop pass, with buzzer silence occurring before any cadence tick. Keep one-action-per-contact debounce and normal occurrence semantics unchanged.

## Boundaries & Constraints

**Always:** Keep active-alert touch handling exclusive; use the painted button geometry as hit-test truth; silence before returning to normal rotation or postponed confirmation; preserve release-latched debounce, repeating alerts, one-time terminal handling, and cooperative non-blocking execution.

**Never:** Change buzzer cadence, alert scheduling/recurrence, postpone duration semantics, screen layout, touch wiring, pin assignments, or claim physical-device behavior from host tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| STOP | Active alert; first stable touch in painted STOP band | Buzzer silences and occurrence resolves in same loop pass | No later cadence tick or replayed action |
| POSTPONE | Active alert; first stable touch in painted POSTPONE band | Buzzer silences and postponed confirmation renders in same loop pass | No later cadence tick or duplicate postpone |
| SHORT_TAP | Valid action touch followed quickly by release | One action succeeds without requiring a held contact or repeated touch | Release latch blocks replay/navigation |
| BOUNCE_OR_GAP | Unstable sample or touch in inter-button gap | Active alert remains active and keeps normal cadence | No false resolution |

</intent-contract>

## Code Map

- `src/device/touch_port.py:31-58` -- polls five raw samples and emits one contact edge; preserve bounded SPI polling while ensuring a valid short action touch is not lost behind an unnecessarily sticky/missed edge.
- `src/ui/touch_calibration.py:34-47` -- converts raw panel coordinates to display coordinates; active action hit tests consume its output.
- `src/app.py:182-237` -- polls touch before `evaluate()` and routes active-alert samples exclusively; same-pass ordering is the responsiveness boundary.
- `src/alert/runtime.py:166-188` -- active-alert hit testing and release latch; `217-354` resolves STOP/POSTPONE and controls buzzer silence/tick ordering.
- `src/ui/alert_view.py:17-31` -- painted STOP/POSTPONE geometry and pure hit helpers; keep hit regions aligned with visible controls.
- `tests/test_alert_app.py:209-370` -- active-alert lifecycle, touch, debounce, silence-before-tick, and re-alert coverage; extend with short-tap and immediate-action regressions.
- `tests/test_touch_port.py` -- bounded sampling and edge semantics; add focused coverage only if polling changes.

## Tasks & Acceptance

**Execution:**
- [x] `src/device/touch_port.py`, `src/ui/touch_calibration.py`, and/or `src/app.py` -- preserve one non-blocking touch poll per loop while preventing valid short action touches from being delayed or discarded -- make action registration responsive on device.
- [x] `src/alert/runtime.py` -- keep STOP/POSTPONE resolution and buzzer silence ahead of cadence, and retain release-latched one-action semantics -- prevent ringing after a recognized action.
- [x] `src/ui/alert_view.py` -- retain or refine pure hit geometry only where needed to match visible action bands -- avoid accidental gap activation.
- [x] `tests/test_alert_app.py` and focused touch tests -- cover first valid short STOP and POSTPONE taps, same-pass silence ordering, release debounce, gap rejection, and existing recurrence semantics -- prove no regression.

**Acceptance Criteria:**
- Given an active alert, when the first valid debounced touch lands in the visible STOP band, then buzzer silence, occurrence resolution, and return to normal rotation happen in that loop pass without requiring continued touching.
- Given an active alert, when the first valid debounced touch lands in the visible POSTPONE band, then buzzer silence and postponed confirmation happen in that loop pass without requiring continued touching.
- Given either action is recognized, when the current loop completes, then no buzzer cadence tick reasserts ringing after silence.
- Given a short valid tap followed by release or bounce, when subsequent samples arrive, then exactly one action occurs and no normal Bar/Settings navigation opens.
- Given a touch in the gap or outside both painted controls, when the alert is active, then it remains active and cadence behavior is unchanged.
- Given repeating and one-time alert members, when STOP or POSTPONE eventually resolves the occurrence, then existing recurrence and canonical one-time disable semantics remain unchanged.

## Design Notes

The fix must distinguish delayed acquisition of a valid contact from action-resolution ordering. Host tests can prove sample-to-action and same-pass ordering; only a flashed Pico can prove panel calibration, short physical taps, buzzer audibility, and measured latency.

## Verification

**Commands:**
- `uv run pytest tests/test_alert_app.py tests/test_touch_port.py tests/test_touch_calibration.py` -- expected: focused alert and touch tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.
- `graphify update .` -- expected: graph refresh succeeds.

**Manual checks (if no CLI):**
- Flash Pico, trigger alert, tap STOP and POSTPONE briefly once each, and record serial/display/buzzer latency separately from host results. Device behavior remains unverified until this run.

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 13 findings — high 0, medium 4, low 0, false 9, maybe-false 0
- findings:
  - `[false]` `[reject]` Runtime files were unchanged — existing `src/alert/runtime.py` already silenced before cadence and existing lifecycle tests covered that ordering.
  - `[medium]` `[patch]` Short STOP tap lacked raw-touch integration coverage — added real `TouchPort` → calibration → `App.step()` STOP test.
  - `[medium]` `[patch]` Short POSTPONE tap lacked raw-touch integration coverage — added real `TouchPort` → calibration → `App.step()` POSTPONE test.
  - `[medium]` `[patch]` Final low-pressure sample discarded stable short contact — accepted stable four-sample prefix for final invalid-pressure sample and added coverage through integration tests.
  - `[false]` `[reject]` Held-contact duplicate edge was not reproduced — `was_down` guard preserves one edge per contact.
  - `[false]` `[reject]` Calibration mapping was not exercised by the first test — existing calibration tests plus new end-to-end action tests cover it.
  - `[false]` `[reject]` Gap coverage was allegedly incomplete — existing hit-helper boundary tests and active-alert gap test cover rejection.
  - `[false]` `[reject]` Replay/navigation coverage was allegedly missing — existing STOP/POSTPONE release-latch tests cover it.
  - `[false]` `[reject]` Sample-count invariant was not added — configured sample count is a fixed positive product constant and no changed behavior exposes an invalid value.
  - `[false]` `[reject]` Physical-device uncertainty required follow-up metadata — manual-device risk is recorded separately; review follow-up recommendation is based on this pass's code findings.
  - `[false]` `[reject]` Tasks were marked complete despite no runtime diff — unchanged runtime already met its ordering task; new tests verify the integration boundary.
  - `[false]` `[reject]` Generated Graphify output obscured the feature diff — repository policy requires `graphify update .` after code changes and generated output is expected.
  - `[medium]` `[patch]` Verification gap for short action integration — added focused STOP/POSTPONE tests using raw sampler, calibration, App, and buzzer.

## Auto Run Result

Status: done

Summary: Touch polling now recognizes stable short taps that release or fall below pressure threshold on the final bounded sample. Added end-to-end host coverage proving raw touch sampling reaches calibrated active-alert STOP and POSTPONE actions in one App step, silences before any later cadence tick, and cannot replay.

Files changed:

- `src/device/touch_port.py` — accepts stable four-sample prefixes on final release/low-pressure samples while preserving debounce and bounded polling.
- `tests/test_touch_port.py` — covers final-sample release edge.
- `tests/test_alert_app.py` — covers raw short STOP/POSTPONE integration and active-button gap rejection.
- `graphify-out/` — refreshed generated code graph after source changes.
- `_bmad-output/implementation-artifacts/alert-clock/spec-active-alert-touch-immediate-response.md` — records plan, review, and verification.

Review findings: 2 patch entries applied, representing 4 medium findings; 9 findings rejected as false with reasons recorded above; 0 deferred.

Follow-up review recommendation: true. Host verification passes, but flashed Pico validation remains required for physical tap latency, calibration, and audible buzzer silence.

Verification:

- `uv run pytest tests/test_alert_app.py tests/test_touch_port.py tests/test_touch_calibration.py` — 34 passed.
- `uv run pytest` — 680 passed.
- `git diff --check` — passed.
- `graphify update .` — passed.
- Device flashing and serial/audio evidence — not performed; behavior remains unverified on hardware.
