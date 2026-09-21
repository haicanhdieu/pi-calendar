# Alert Clock Architecture Spine — Rubric Review

Reviewed: 2026-09-21  
Reviewer: architecture rubric walker  
Scope: `ARCHITECTURE-SPINE.md`, Alert Clock PRD/addendum, Alert Clock UX
`DESIGN.md` and `EXPERIENCE.md`, inherited core/Wi-Fi/touch spines.

## Verdict

**Changes required before final.** Deterministic lint passes with zero
findings; source coverage and inherited constraints are broadly sound. One
load-bearing surface-state seam remains under-specified and currently conflicts
with PRD/UX-required return-to-Rotation behavior.

## Mechanical Gate

`uv run .agents/skills/bmad-architecture/scripts/lint_spine.py --workspace
_bmad-output/planning-artifacts/alert-clock/architecture`

Result: `ok: true`, 0 findings.

## Checklist Assessment

| Check | Result | Notes |
| --- | --- | --- |
| Real lower-level divergence points fixed | Partial | Scheduling, persistence, timing, hardware boundary, and failures are well-bound. Active-alert integration with inherited touch state remains open. |
| Every AD rule enforceable / prevents stated divergence | Partial | AD-6 establishes exclusive ownership, but omits state handoff and terminal destination. |
| Deferred items safe | Pass | Hardware drive and user-facing failure wording are correctly deferred behind explicit validation conditions. |
| PRD/UX capabilities covered | Partial | Most FR/NFR coverage is explicit. FR-6–FR-9 / UX State Patterns conflict with AD-6 on terminal surface. |
| Brownfield/inherited spines ratified | Pass | Core functional boundary, App ownership, display contract, settings persistence, web ownership, and touch/SPI rules are inherited without override. |
| Named technology current | Pass | Official Pico W download page lists MicroPython v1.29.0 as latest stable on 2026-09-21; preview v1.30 is not stable. |
| Feature-owned dimensions decided/deferred/open | Partial | Runtime, persistence, UX, hardware safety, and failure recovery are covered. Existing touch-state integration needs an explicit decision. |

## Findings

### High — AD-6 does not define active-alert handoff to inherited touch surface state

**Disposition: autofix.**

AD-6 says active alert preempts normal surfaces and their deadlines, then
“returns control to existing normal surface lifecycle.” This leaves two builders
free to choose incompatible designs: add `active-alert` to inherited
`active_surface` (whose valid values are explicitly `rotation`, `bar`,
`settings`), or retain hidden `bar`/`settings` while a separate alert flag gates
rendering and touch. It also permits return to a previously hidden Settings or
Bar surface.

That outcome conflicts with PRD FR-7/FR-9 and UX State Patterns, which require
terminal Stop/Auto-stop to return to **Normal Rotation**; UX also requires
Postpone confirmation then Normal Rotation. It risks stale normal-surface
deadlines/taps reclaiming or resolving an active alert.

**Required rule shape:** bind the `App.step()` insertion/gating seam with
touch-ui AD-5/AD-6/AD-9. State whether alert state is a separate App-owned
gate (recommended) or an extension to touch state. On raise, gate all normal
surface hit-testing, idle, and rotation deadline handling. Route only alert
hit-tests while active. On Stop/Auto-stop and after Postpone confirmation, set
normal surface to `rotation`, re-arm current base-view dwell from `now`, and
discard hidden Bar/Settings interaction state. Define same ordering for
rendering so no normal overlay renders above active alert.

### Medium — Capability map omits explicit proof/test ownership for NFR-6

**Disposition: autofix or defer with revisit condition.**

Consistency conventions distinguish host and flashed-device evidence, and
AD-7/AD-8 require bounded hardware behavior. But structural seed and capability
map assign no test/proof location or owner for NFR-6's required host scheduler
tests plus device evidence (cadence, controls, Auto-stop, Postpone, collision,
reboot persistence, offline operation). Independently-built implementation and
test units can diverge on evidence scope.

Add a map row naming `tests/` for pure/fake-port tests and active
`alert-clock` implementation/test artifacts for flashed-device evidence; or add
an explicit Deferred item with those exact acceptance cases and a pre-release
revisit condition.

### Low — AD-1 wording leaves postponed-plus-new-due ordering implicit

**Disposition: discuss or clarify in AD-1.**

“Due while alert is active” does not describe a normal base Alert becoming due
while a postponed occurrence is pending (not active), nor a postponed re-alert
and base due events detected in same tick. Existing wording supports one active
occurrence, but not deterministic membership/order at those boundaries.

Clarify scheduler batch ordering: collect all due sources for one scheduler
pass, join them if activation occurs, retain one pending postpone independently
until it raises, and never create two active occurrences. If this behavior is
intentional implementation detail rather than cross-unit contract, defer it
explicitly.

## Strengths

- AD-1 through AD-5 make collision, restart, configuration, record ownership,
  civil-time, and monotonic-time decisions concrete.
- AD-7 preserves pure-domain/device-adapter separation and blocks unsafe PWM
  commitment pending physical proof.
- AD-8 preserves loop recovery and diagnosability without exposing secrets.
- Stack pin is current and source-linked; no unpinned named dependency found.
