# PRD Quality Review — Alert Clock

## Overall verdict

Strong hobby-scale feature PRD: product outcome, bounded scope, primary journeys, persistence, and target-device safety constraints are unusually concrete. Not build-ready yet: hardware control contract is explicitly unresolved, while collision/lifecycle rules leave combined one-time and repeating alerts ambiguous. Resolve phase blocker and state model before architecture.

## Decision-readiness — thin

PRD makes clear decisions on max ten alerts, browser-only configuration, touch-only response, five-minute Auto-stop, and default Postpone duration. Trade-off is visible in §5: no GPIO/wiring decision before physical board verification. §9 honestly names hardware as phase blocker.

Collision decision in FR-4 is stated but lifecycle effect is not: one combined occurrence can contain alerts with different recurrence and one-time state. Stop/Postpone/Auto-stop "resolves all matched Alerts together," yet PRD does not define which one-time configurations disable and how one postponed combined occurrence is persisted. Decision-maker cannot yet assess user-facing trade-off between combined and sequential handling.

### Findings

- **high** Combined-occurrence lifecycle undefined (§4.2 FR-4; §4.3 FR-8) — Same-time alerts combine, but one-time/repeating combinations and Postpone persistence lack deterministic outcome. *Fix:* Define combined occurrence membership, each member's completion/disable rule, and whether Postpone creates one shared occurrence or per-alert deferred records.
- **high** Hardware contract blocks architecture (§9.1; addendum Hardware Research) — Required module identity, pin order, supply/current, and GPIO-drive safety are unavailable. *Fix:* Inspect/bench-test supplied module; record verified wiring and electrical/control facts in `docs/hardware_configuration.md`; then close blocker.

## Substance over theater — strong

Vision (§1) is device-specific: no reflash, authenticated web settings, local TFT controls, and normal display restoration. NFRs (§7) carry Pico-specific boundaries: pure CPython scheduler logic, non-blocking loop, 3.3 V GPIO safety, serial diagnostics, and separate host/device evidence. No persona, innovation, or generic scalability theater.

## Strategic coherence — adequate

Thesis holds: make existing clock useful as unattended desk alarm without expanding it into cloud/mobile alarm platform. Features support this arc, while §5 rejects phone notifications, labels, custom sounds, and per-alert controls. Success metrics validate key behavior; counter-metrics protect existing clock, web, Wi-Fi, and touch use.

Metrics remain demonstrative rather than acceptance-calibrated: “continues displaying/responding” in SM-3 duplicates unbounded NFR-2 and cannot distinguish a healthy loop from a sluggish one. Appropriate for hobby stakes, but device validation needs observable checkpoints.

### Findings

- **medium** Responsiveness success criterion lacks observable bound (§7 NFR-2; §8 SM-3) — “responsive” has no testable latency or defined interaction while alarm sounds. *Fix:* Specify a target-device observable rule, e.g. Stop/Postpone accepted on first valid tap and UI change within a stated deadline, with serial checkpoints for failure.

## Done-ness clarity — thin

Most FRs have useful consequences: max-alert behavior, save validation, persistence, weekday matching, duplicate-minutes, preemption, and auto-stop are testable. FR-5 appropriately refuses unsafe pin assumptions and separates host from hardware tests.

Several critical requirements use subjective or underspecified terms: buzzer “repeating audible cadence,” Stop “immediately,” controls “large,” and touch debouncing “enough.” Alert timing also lacks precision for scheduler polling: what exact wall-clock instant triggers, and what happens if time source jumps forward/backward or config changes at matching minute. These gaps will produce divergent architecture and tests.

### Findings

- **high** Alarm timing/state transition contract incomplete (§4.2 FR-4; §4.3 FR-9) — Scheduler-cycle timing, clock corrections, and state transition semantics do not fully determine when an occurrence fires or is suppressed. *Fix:* Define a stable occurrence key and due rule (date/time/alert identity), behavior for forward/backward clock changes, and restart state reconciliation.
- **medium** UI/audio acceptance criteria subjective (§4.2 FR-5; §4.3 FR-6–FR-8) — “audible cadence,” “large,” “immediately,” and “enough” are not verifiable. *Fix:* Define cadence behavior, minimum touch-target/layout constraints, and measurable/observable action-response criteria.

## Scope honesty — adequate

§5/§6 make meaningful omissions explicit, including physical buttons, remote notifications, custom sounds, per-alert Postpone, and hardware-specific wiring. Assumptions are marked inline and indexed. Four open items separate one phase blocker from non-blockers.

For draft intended to feed downstream work, open collision and overdue-restart behavior influence persistence/state design rather than merely polish. They are labelled non-blocking but should be resolved before stories because developers otherwise choose incompatible models.

### Findings

- **medium** Architecture-affecting assumptions treated as non-blockers (§9.2, §9.4) — Collision and post-reboot overdue policies govern storage/state model. *Fix:* Confirm before architecture, or explicitly instruct architecture to select/document policy and retain migration-safe model.

## Downstream usability — adequate

Domain glossary defines Alert, Occurrence, Active alert, Postpone, delay, and Auto-stop; UJ protagonists are named; FR-1 through FR-9, UJ-1 through UJ-4, NFR-1 through NFR-6, and SM-1 through SM-3 are contiguous. Existing-product references in §0 make brownfield scope clear.

Cross-PRD terms depend on linked documents, which is acceptable but should be verified during architecture. Glossary uses “Alert,” “Occurrence,” and “Active alert” consistently. “Postpone” is consistently preferred over snooze after glossary declaration.

### Findings

- **low** No explicit persistence data boundary (§4.1–§4.3) — Downstream implementation must infer alert IDs, ordering, recurrence encoding, and atomic persistence behavior. *Fix:* Put technical data-model options in addendum or require architecture to define them; retain PRD-level behavioral identity semantics.

## Shape fit — strong

Hobby, single-owner, brownfield hardware feature receives light but sufficient form: four real journeys, concise capability sections, concrete non-goals, and hardware safety evidence. User journeys are load-bearing because alert response is meaningful touch UX. PRD avoids enterprise process overhead while preserving UX/architecture/story inputs.

## Mechanical notes

- All inline `[ASSUMPTION]` tags appear represented in §10; §9 overdue-restart assumption is indexed separately.
- IDs contiguous and unique. Cross-PRD relative links appear structurally plausible but were not link-checked in this rubric pass.
- Required hobby/brownfield sections present: vision, journeys, glossary, FRs, non-goals, scope, NFRs, success metrics, assumptions, open questions.
- `status: draft` matches unresolved phase blocker.
