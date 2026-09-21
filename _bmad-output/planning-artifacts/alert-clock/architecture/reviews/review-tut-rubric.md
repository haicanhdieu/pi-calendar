# Alert Clock Architecture Spine — `tut` Cadence Rubric Review

Reviewed: 2026-09-21  
Reviewer: architecture rubric walker  
Scope: `ARCHITECTURE-SPINE.md` after direct-GPIO `tut` cadence amendment;
Alert Clock PRD; hardware source of truth; inherited core, Wi-Fi, and touch
spines.

## Verdict

**Changes required before final handoff.** Direct-GPIO cadence is bounded,
non-blocking, and placed at the correct device boundary. Two shared-authority
records remain contradictory: the parent settings schema and hardware source
of truth.

## Mechanical Gate

`uv run .agents/skills/bmad-architecture/scripts/lint_spine.py --workspace
_bmad-output/planning-artifacts/alert-clock/architecture`

Result: `ok: true`, 0 findings.

## Good-Spine Checklist

| Check | Result | Notes |
| --- | --- | --- |
| Real lower-level divergence points fixed | Partial | AD-5/AD-7 fix cadence owner, duration source, GPIO, and failure boundary. Shared record authority still splits. |
| Every AD rule enforceable / prevents stated divergence | Partial | AD-7 is enforceable. AD-4 cannot coexist with inherited Wi-Fi AD-3 as written. |
| Deferred items safe | Fail | Updating parent Wi-Fi settings contract is deferred even though it is required for any alert-record build. |
| PRD capabilities covered | Pass | FR-5 exact 180 ms high / 220 ms low repeating `tut` cadence lands in AD-5, AD-7, stack, seed, map, and Deferred. |
| Brownfield / inherited spines ratified | Partial | Core and touch boundaries remain compatible. Wi-Fi AD-3 is contradicted by alert settings version migration. |
| Named technology current | Pass | Official Pico W release page lists MicroPython `v1.29.0` as latest stable on review date. No new PWM dependency is bound. |
| Feature-owned dimensions decided/deferred/open | Partial | Cadence, recovery, and electrical deployment gate are covered; hardware source-of-truth evidence/state is stale. |

## Findings

### High — Alert AD-4 contradicts inherited Wi-Fi settings authority

**Disposition: autofix.**

Alert AD-4 requires `SettingsStore` to migrate valid
`settings_version: 1` records to an alert-capable next version and accept
alert fields. Inherited Wi-Fi AD-3 instead permits only a canonical version-1
record with its enumerated fields and says every unsupported record is treated
as unconfigured. The Alert spine defers changing that parent rule, but this is
a current cross-unit contract conflict, not safe deferred work.

**Required rule shape:** update Wi-Fi AD-3 before implementation to define the
canonical alert-capable version, v1 migration/defaults, old-firmware behavior,
backup/quarantine handling, and the sole validation/commit path. Then have
Alert AD-4 cite that shared contract rather than locally extending it.

### High — Hardware source of truth still says buzzer validation is pending

**Disposition: autofix.**

Alert AD-7 says direct 3.3 V GP15 audibility is bench-confirmed and recorded
in `docs/hardware_configuration.md`. That document still labels GP15 as
"PWM/control signal", says firmware control remains disabled until bench checks
pass, and lists audible-output testing as future work. Firmware builder can
therefore follow hardware source of truth and omit/reject direct-GPIO `tut`
operation, while another follows Alert spine.

**Required rule shape:** update hardware record to say direct-GPIO `tut`
audibility was observed, replace PWM-only wording with direct-GPIO control,
and retain current measurement, control polarity, and electrical-safe-drive as
separate deployment gates. Record serial/device evidence location if available.

## Confirmed Cadence Fit

- `BuzzerPort.tick(now, sounding)` owns 180 ms-high / 220 ms-low transitions;
  pure alert state remains hardware-free.
- Wrap-safe monotonic timing owns cadence and Auto-stop; local civil time owns
  only due detection.
- GP15 does not collide with documented TFT/touch GPIO assignments.
- Cadence ends through immediate silence on every terminal/failure path.

## Sources Checked

- `ARCHITECTURE-SPINE.md` AD-4, AD-5, AD-7, Stack, Structural Seed, Deferred.
- Alert Clock PRD FR-5 and NFR-4.
- `docs/hardware_configuration.md`, HW-508 wiring and software notes.
- Wi-Fi-config spine AD-3; core and touch inherited rules.
- Official MicroPython Pico W releases: `v1.29.0` current stable on
  2026-09-21.
