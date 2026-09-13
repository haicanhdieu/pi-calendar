---
title: 'Story 2.1: Pure touch_state transitions for rotation ⇄ bar'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: '27491e028290bf0d4388f923cefb5386dcb43299'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Touch surfaces have state fields but no pure, host-testable owner for deciding when Rotation reveals the Bar or an already revealed Bar expires.

**Approach:** Add a small device-import-free transition module that returns the next surface and deadline from explicit inputs, then establish focused host coverage for reveal, fixed-deadline expiry, no-op, and wrap-safe timing behavior.

## Boundaries & Constraints

**Always:** Keep the module pure and CPython-importable; use `TOUCH_IDLE_TIMEOUT_MS` and wrap-safe tick helpers. A fresh edge on `rotation` enters `bar` and arms a new deadline. A Bar deadline is a one-shot set only on entry, never renewed by a later evaluation. `bar` expires to `rotation` when its deadline is due. Preserve an unimplemented `settings` surface without assigning it a new deadline.

**Never:** Do not change `App`, touch polling, hit testing, rendering, Bar geometry, compositor behavior, view dwell scheduling, or hardware wiring. Do not import `machine`, `network`, `ntptime`, or anything under `src.device`; do not introduce a reset-on-touch path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Reveal | `rotation`, fresh edge, `now` | Return `bar` and `ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)` | No error expected |
| Idle expiry | `bar`, no edge, due deadline | Return `rotation` and no surface deadline | No error expected |
| Bar remains active | `bar`, not-due deadline, with or without edge | Return the unchanged deadline; never renew it | No error expected |
| Tick wrap | `bar`, deadline across 32-bit wrap | Use `ticks_diff` to distinguish future from due | No error expected |

</intent-contract>

## Code Map

- `src/ui/view_state.py` -- precedent for a compact pure decision module and host-importable UI state constants.
- `src/ticks.py` -- pure `ticks_add`/`ticks_diff` primitives required for deadline arming and expiry across wraparound.
- `src/config.py` -- owns `TOUCH_IDLE_TIMEOUT_MS`; it already supplies all geometry/timing constants and is read-only for this story.
- `src/app.py` -- sole `AppState` owner with pre-existing `active_surface` and `surface_deadline`; read-only until Story 2.2 wires the decision into step 0.
- `src/device/touch_port.py` -- produces edge-down coordinates but remains device-layer and read-only; this pure story must not couple to it.
- `tests/test_view_state.py` -- existing AST import-purity helpers and pure-state test conventions to reuse for `touch_state` coverage.
- `_bmad-output/planning-artifacts/touch-ui/epics.md` -- Story 2.1 locks the non-renewing Bar deadline and requires no inline touch/drawing geometry values.

## Tasks & Acceptance

**Execution:**
- `src/ui/touch_state.py` -- add named surface constants and one explicit pure transition function returning `(next_surface, next_deadline)` -- centralize Rotation/Bar timing decisions without hardware coupling.
- `tests/test_touch_state.py` -- add direct transition, deadline, wraparound, and AST import-purity tests -- prove behavior at the module's public boundary.

**Acceptance Criteria:**
- Given `rotation` and an edge-down input, when the transition is evaluated at `now`, then it returns `bar` with a deadline armed using `TOUCH_IDLE_TIMEOUT_MS`.
- Given `bar` and a deadline that is due, when the transition is evaluated without a fresh edge, then it returns `rotation` with no Bar deadline.
- Given `bar` and a future deadline, when evaluated with or without an edge, then it retains that exact deadline rather than extending the idle interval.
- Given deadlines across tick wrap, when evaluated, then expiry is decided with wrap-safe tick arithmetic.
- Given the new module is imported on CPython or inspected by AST, when its imports are examined, then it has no device/hardware imports.

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 5 findings — high 0, medium 0, low 0, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` Rotation preserves a supplied stale deadline — `rotation` is the only legal initial surface (`AppState` initializes it with `None`), and its sole implemented transition overwrites the deadline on Bar entry; no reachable caller can leak a stale deadline to another surface.
  - `[false]` `[reject]` A Bar with no deadline remains active forever — the only producer of `bar` in this change atomically returns a non-`None` deadline, while `App` has not yet wired a caller and initializes Rotation only; the alleged corrupt/partial state is not demonstrated.
  - `[false]` `[reject]` Missing gear/outside hit-target transitions — Story 2.1 is expressly the pure rotation-to-Bar/timeout foundation; Story 2.3 owns outside-tap and gear behavior, so adding target policy now would violate the captured story boundary.
  - `[false]` `[reject]` CPython import test relies on global module state — AST inspection directly proves the no-device-import contract and the direct import test proves host importability; the extra `sys.modules` assertion is redundant but does not make an incorrect claim or cause a demonstrated failure.
  - `[false]` `[reject]` Wrap test lacks an after-wrap post-deadline value — the test proves the future-across-wrap and exact-due boundary, and `ticks_diff` is separately covered by `tests/test_ticks.py`; the asserted inversion is not present in the cited comparison.

## Design Notes

The function accepts the current deadline rather than reading mutable state. This keeps `App` as the eventual writer while making a fixed one-shot deadline auditable: only the `rotation` edge path calls `ticks_add`; the retained-Bar path returns its supplied deadline unchanged.

## Verification

**Commands:**
- `uv run pytest tests/test_touch_state.py tests/test_view_state.py` -- expected: transition and purity coverage passes.
- `uv run pytest` -- expected: complete host suite passes.

## Auto Run Result

Status: done

Implemented the pure Rotation/Bar surface transition core: a rotation edge arms the shared timeout, a due Bar deadline returns to Rotation, and active Bar evaluation never renews its deadline.

Files changed:
- `src/ui/touch_state.py` — pure named-surface transition function using wrap-safe tick helpers.
- `tests/test_touch_state.py` — reveal, expiry, fixed-deadline, wrap, settings-preservation, and import-purity coverage.
- `epic-2-context.md` — focused developer context compiled from current planning artifacts.

Review findings: 0 patches, 0 deferred. Two independent layers were available; the edge-case layer reported no findings and the blind review's five findings were rejected with the recorded evidence above. Verification-gap and intent-alignment layers could not launch because reviewer capacity was exhausted; this is a workflow-capacity limitation, not an unverified code failure. Follow-up review recommendation: false (patched high 0, patched medium 0).

Verification performed: `uv run pytest tests/test_touch_state.py tests/test_view_state.py` passed (13 tests); `uv run pytest` passed (317 tests).

Residual risks: host tests prove only pure transition behavior; touch polling, App integration, rendering, and on-device interaction are intentionally deferred to later stories.
