# PRD and Brief Reconciliation

**Spine:** `../ARCHITECTURE-SPINE.md`  
**Inputs:** `prds/prd.md`, `briefs/brief.md`, `briefs/addendum.md`  
**Date:** 2026-09-06  
**Verdict:** **Substantially reconciled, with three material omissions and two source conflicts that the spine currently resolves silently.** FR-1–FR-3, the functional-core constraint, fixed Vietnam time, bounded rendering, failure degradation, credential isolation, tested hardware ownership, and the lunar-ready cell boundary all landed.

## Material Findings

### RPB-1 — Periodic re-sync after success did not land as a binding behavior

**Source requirement:** The PRD requires NTP sync “on boot and on a recurring interval” (`prd.md` §4.1), and the brief likewise requires boot sync with periodic re-sync. Retry while unsynced is only one case of this lifecycle.

**Spine landing:** AD-5 binds “NTP retry”; AD-8 schedules retry after recoverable failures. Neither requires a previously successful device to re-sync periodically. `last-sync age` is published, but the policy using it is Deferred.

**Impact:** A builder can implement one successful boot sync and never contact NTP again while satisfying the literal ADs. That misses FR-1 and the product goal of controlling clock drift.

**Recommended reconciliation:** Amend the sync rule to distinguish recurring re-sync while trusted from retry while untrusted. Exact durations can remain checked-in configuration; the lifecycle itself cannot.

### RPB-2 — Never-synced cold boot has no representable time state

**Source requirement:** The brief explicitly treats “never synced” as untrustworthy and identifies the Pico’s cold-boot epoch as a known wrong date. The PRD says failure continues from the last known source, which presumes one exists.

**Spine landing:** AD-3 requires every `TimeSnapshot` to contain a UTC instant and permits only `synced | unsynced`. AD-8 advances the “last wall-time.” With the v1 RTC deferred, cold boot plus NTP failure has neither a valid instant nor a last known time.

**Impact:** Time and UI units can diverge between showing the false RP2040 epoch, blanking, showing placeholders, or treating the epoch as stale. The brief’s “do not confidently show wrong time” intent is not guaranteed by an `UNSYNCED` flag alone.

**Recommended reconciliation:** Add explicit initial availability/origin semantics and bind the pre-first-sync rendering contract. Freshness threshold after a valid sync may remain a separate policy question.

### RPB-3 — The addendum’s once-per-day solar-term rule disappeared

**Source constraint:** The addendum states that solar-term computation “should be treated as a once-per-day cached calculation from the outset, never as a per-render call.” The brief names per-render solar math on the RP2040 as an architectural performance risk.

**Spine landing:** Lunar conversion strategy is Deferred, and AD-6 provides generic annotations, but solar-term computation ownership/cadence is neither decided nor explicitly deferred.

**Impact:** The current spine is intentionally shaped for later Vietnamese calendar enrichment, yet a future provider and renderer can independently place this expensive computation on different paths, including the render path expressly ruled out by the source.

**Recommended reconciliation:** Preserve this as an inherited future-phase constraint now: enrichment providers compute/cache date-derived annotations outside rendering, at most once per affected local date. The algorithm may remain Deferred.

## Source Conflicts Currently Resolved Silently

### RPB-4 — Button versus no-button v1 scope

**Conflict:** The brief calls one push button a settled v1 decision, and the addendum proposes GP15 plus debounce behavior. The PRD instead places physical input out of scope and retains “no buttons” as an assumption/open question.

**Spine landing:** The spine implements clock-dominant automatic rotation and has no input adapter, effectively choosing the PRD/no-button direction. It does not record that it is superseding the brief’s explicit decision.

**Impact:** Readers following the brief can reasonably expect a button story and `src/device/input/`; readers following the spine will not build either.

**Recommended reconciliation:** Record source precedence and the settled v1 choice in the upstream PRD/brief or in a short spine constraint. If no button is the final decision, update the brief/addendum so cited inputs stop disagreeing.

### RPB-5 — Unsynced indicator presentation conflicts inside the cited brief package

**Conflict:** The brief requires a visible trust indicator but does not fix its form. The addendum says it “should be non-textual and ambient.” The spine calls it a badge but leaves presentation unspecified; the separately cited finalized UX uses an explicit textual `UNSYNCED` badge.

**Impact:** This is not an architecture invariant, but it is a source reconciliation issue: a renderer built from the addendum could intentionally avoid text while one built from UX uses required text.

**Recommended reconciliation:** Treat finalized UX as authoritative and update/remove the addendum’s non-textual direction. The spine should continue delegating exact presentation to UX rather than duplicating it.

## Quiet Product Intent Not Carried Forward

### RPB-6 — Alarm is absent from Deferred despite being called “emotionally load-bearing”

**Source intent:** The PRD excludes alarm/buzzer from v1 but explicitly says it is a real future direction and the first item to revisit once clock/calendar is stable. The brief also lists alarms out of v1.

**Spine landing:** The scope and Deferred section preserve lunar and RTC evolution but never mention alarm/input evolution.

**Impact:** No v1 boundary needs to be generalized for an alarm today, but omission from the architecture trail makes this priority easy to lose and makes the spine appear to select lunar as the only future product direction.

**Recommended reconciliation:** Add alarm/buzzer as explicitly outside this spine, with the PRD’s revisit trigger. Do not introduce alarm architecture until its requirements exist.

## Confirmed Landings

| Input requirement / constraint | Spine landing | Result |
| --- | --- | --- |
| Raspberry Pi Pico W + MicroPython | Stack, AD-1, AD-10 | Correct |
| Clock, seconds, weekday/date | FR-2 map; one-second scheduling/rendering | Correct |
| Gregorian current-month grid, Monday-first, leap-year-capable | AD-6 and FR-3 map | Correct |
| Wi-Fi/NTP in v1 | AD-3–AD-5, AD-8, capability map | Partial only because recurring successful re-sync is missing |
| Fixed Vietnam UTC+7 | AD-4 | Correct |
| Trust visibly distinguished; failures do not crash/freeze | AD-3, AD-8, badge map | Partial only because never-synced availability is absent |
| No full framebuffer; low steady-state allocation | AD-7 | Correct |
| Pure logic imports unchanged on CPython | AD-1, AD-10 | Correct |
| Wi-Fi credentials outside version control | AD-9 | Correct |
| Controller identity must be verified | Stack assumption + Deferred controller probe | Correct |
| Hardware pins/SPI/MADCTL change only with physical docs | hardware source-of-truth statement | Correct |
| Landscape current implementation | structural diagram and delegated hardware source | Correct against current hardware; supersedes the draft brief’s portrait uncertainty |
| DS3231 outside v1 but integration reserved | Deferred plus AD-3/AD-4 | Correct |
| Lunar capability added without rewriting Gregorian grid | AD-6 | Direction landed; concrete annotation-item compatibility needs separate architecture tightening |
| No telemetry/instrumentation for hobby v1 | diagnostics convention | Correct |
| Device deployment must be physically verified | device-layout convention + Operational proof Deferred item | Correct |
| Glance-first, single-purpose, no decorative complexity | clock-dominant rotation and bounded rendering | Correct at architecture altitude; visual/interaction tone belongs to UX |

## Reconciliation Order

1. Fix RPB-1 and RPB-2 before FR-1 implementation stories are accepted.
2. Resolve RPB-4 upstream so the cited PRD and brief agree on input hardware.
3. Preserve RPB-3 as a future-enrichment invariant or explicit Deferred decision.
4. Correct the addendum for RPB-5 and retain alarm intent per RPB-6 without designing it prematurely.
