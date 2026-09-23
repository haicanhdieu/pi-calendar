---
title: 'Recover active alert after postpone and re-alert'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - _bmad-output/planning-artifacts/alert-clock/prds/prd.md
  - _bmad-output/planning-artifacts/alert-clock/architecture/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md
warnings: []
deferred: []
baseline_revision: '86eaf968a9240a3dbdc7cf56d33f9224ac5075d5'
---

<intent-contract>

## Intent

**Problem:** After a user postpones an alert, the next alert at the postponed due time can leave the TFT on the active-alert screen with continuous buzzer output and no effective touch response. Recovery currently requires power cycling.

**Approach:** Make the Postpone transition fully reset transient active-alert touch and surface state before the later occurrence, then prove a second active occurrence accepts STOP or POSTPONE and still reaches bounded auto-stop recovery.

## Boundaries & Constraints

**Always:** Preserve one-action-per-contact debounce, active-alert priority, five-minute monotonic auto-stop, buzzer silence before resolution, persisted postpone semantics, repeating-alert behavior, and cooperative non-blocking loop execution.

**Never:** Change buzzer cadence, postpone duration meaning, alert recurrence rules, display geometry, hardware pins, or claim physical-device behavior from host tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| POSTPONE_THEN_REALERT | Active alert receives one valid Postpone touch, then reaches deferred due time | Confirmation exits to normal rotation; later occurrence renders active alert, buzzer cadence starts, and touch response works | No stale latch/surface state may strand the loop |
| REALERT_STOP | Second occurrence receives valid STOP touch | Buzzer silences and screen returns to normal rotation in same loop pass | No duplicate action or later cadence tick |
| REALERT_AUTOSTOP | Second occurrence receives no action for five monotonic minutes | Buzzer silences and normal rotation resumes | Wall-clock changes do not extend or remove timeout |
| RELEASE_BOUNDARY | Postpone contact releases across a loop boundary before re-alert | Release clears transient touch state without replaying navigation or action | Malformed/missing samples remain bounded |

</intent-contract>

## Code Map

- `src/app.py:172-237` -- polls touch before alert evaluation; routes active alerts through alert touch handling and carries `surface_deadline` across transitions.
- `src/alert/runtime.py:160-190` -- active-alert hit testing, release latch, and sentinel surface state; Postpone resolution at `291-317` must clear transient state before re-alert.
- `src/alert/runtime.py:328-350` -- monotonic auto-stop and buzzer silence path; must remain reachable after a postponed re-alert.
- `src/device/touch_port.py:31-68` -- bounded raw touch edge semantics; preserve one edge per physical contact and release behavior.
- `tests/test_alert_app.py:407-470` -- existing Postpone/re-alert and release-latch tests; extend with a second-occurrence action and no-action auto-stop regression using realistic touch state.
- `tests/test_touch_port.py` -- edge/release behavior; add coverage only if the fix changes raw touch state handling.

## Tasks & Acceptance

**Execution:**
- `src/alert/runtime.py` and/or `src/app.py` -- reset active-alert-only touch latch/surface sentinels at Postpone resolution and reinitialize them when a deferred occurrence raises -- prevent stale state from blocking later touch handling.
- `tests/test_alert_app.py` -- add regression coverage for Postpone, deferred re-alert, second-occurrence STOP/POSTPONE, and five-minute auto-stop -- prove recovery without power-cycle-equivalent reinitialization.

**Acceptance Criteria:**
- Given an active alert and a valid Postpone action, when the postponed due time arrives, then the second active-alert screen renders and its buzzer starts without inheriting stale touch/surface state.
- Given that second active occurrence, when a valid STOP touch arrives, then the buzzer silences, the occurrence resolves, and normal rotation returns in that loop pass.
- Given that second active occurrence, when no touch action occurs for five monotonic minutes, then auto-stop silences the buzzer and normal rotation returns.
- Given a Postpone touch followed by release, when later normal or active-alert loops run, then the original contact cannot replay an action or block a new valid contact.
- Given existing repeating and persisted-postpone flows, when the regression fix runs, then alert membership, postpone persistence, cadence timing, and one-time disable semantics remain unchanged.

## Design Notes

Transient fields (`_alert_touch_latched`, `surface_deadline`, and active-alert start state) must have explicit lifecycle ownership. A fix must distinguish contact-release cleanup from active-occurrence reset so held-contact debounce remains safe while a later physical tap can be accepted.

## Verification

**Commands:**
- `uv run pytest tests/test_alert_app.py tests/test_touch_port.py tests/test_touch_calibration.py` -- expected: focused alert/touch tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.
- `graphify update .` -- expected: graph refresh succeeds.

**Manual checks (if no CLI):**
- Flash Pico, postpone a repeating alert, wait for re-alert, verify STOP/Postpone touch and five-minute auto-stop; record serial/display/buzzer evidence separately because host tests cannot prove hardware behavior.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 12 findings — high 0, medium 3, low 0, false 9, maybe-false 0
- findings:
  - `[false]` `[reject]` Generated Graphify output appears unrelated — repository policy requires refreshing and retaining root graph output after code changes; generated churn is expected.
  - `[false]` `[reject]` Release-pending state could block recovery while contact remains held — `t()` treats the next non-edge sample as release and clears the pending state; a held contact cannot permanently strand the loop.
  - `[false]` `[reject]` Postpone resets latch but not release-pending state — this distinction is intentional: pending state prevents replay until the next non-edge sample, then clears before a later occurrence.
  - `[false]` `[reject]` STOP and auto-stop omit explicit transient cleanup — both clear active state and the next cooperative touch poll clears release state; re-alert initialization resets the active surface/latch state.
  - `[medium]` `[patch]` Second re-alert POSTPONE action lacked coverage — patch adds a second-occurrence POSTPONE regression asserting deferred state and buzzer silence.
  - `[low]` `[reject]` Auto-stop test lacks pre-deadline and exact-boundary assertions — direct source logic and existing boundary-oriented timeout tests make extra coverage low value for this bug.
  - `[low]` `[reject]` Auto-stop test lacks a wall-clock jump — implementation uses monotonic ticks by design; this is redundant coverage, not a demonstrated defect.
  - `[low]` `[reject]` Second STOP test lacks display/cadence assertions — existing active render and cadence tests cover those contracts; this test targets lifecycle recovery.
  - `[low]` `[reject]` New tests use ad-hoc touch fakes — existing raw TouchPort/calibration integration tests cover physical sampling; lifecycle regression does not need duplicate plumbing.
  - `[low]` `[reject]` Matrix error row lacks malformed-sample re-alert coverage — bounded malformed-sample behavior is covered by existing touch/App tests and no changed path expands that risk.
  - `[medium]` `[patch]` Second re-alert POSTPONE action lacked coverage — same root cause as first patch entry; add one focused test covering repeat postpone.
  - `[medium]` `[patch]` Second-occurrence STOP test did not assert normal rotation — patch adds `active_surface == "rotation"` after STOP.

## Auto Run Result

Status: done

Summary: Reset transient active-alert touch/surface state across Postpone and deferred re-alert transitions. Added release gating so a prior contact cannot replay or strand later alert handling. Added repeat Postpone, repeat STOP, release-boundary, and monotonic auto-stop regressions.

Files changed:

- `src/alert/runtime.py` — lifecycle reset/release handling for active-alert touch state.
- `src/app.py` — routes touch samples through release-pending handling.
- `tests/test_alert_app.py` — second-occurrence action and auto-stop regression coverage.
- `graphify-out/` — refreshed generated repository graph.
- `_bmad-output/implementation-artifacts/alert-clock/spec-postpone-realert-stuck-alert.md` — build-auto plan, review, and evidence.

Review findings: 3 medium patch entries applied (two repeat-Postpone coverage entries share one fix, plus STOP rotation assertion); 9 findings rejected with reasons recorded in the triage log; 0 deferred.

Follow-up review recommendation: true. Three medium review findings were patched. Residual risk is physical Pico validation: host tests cannot prove TFT touch acquisition, buzzer GPIO silence, cadence, heap behavior, or power-cycle-free recovery.

Verification:

- `uv run pytest tests/test_alert_app.py tests/test_touch_port.py tests/test_touch_calibration.py` — 37 passed.
- `uv run pytest` — 683 passed.
- `git diff --check` — passed.
- `graphify update .` — passed; generated graph refreshed.
- Matrix audit — all four rows covered by passing tests: Postpone/re-alert, repeat STOP, auto-stop, and release boundary.
- Device flashing and serial evidence — not performed; required before claiming on-device behavior.
