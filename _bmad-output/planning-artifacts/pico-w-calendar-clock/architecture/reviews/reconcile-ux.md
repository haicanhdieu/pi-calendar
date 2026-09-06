# Finalized UX Reconciliation

**Inputs:** `DESIGN.md`, `EXPERIENCE.md` (both `status: final`)  
**Artifact checked:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-06  
**Verdict:** **GAPS TO RESOLVE BEFORE FINALIZATION**

The spine carries the visual-system ownership, local-time boundary, calendar
shape, rendering-memory constraint, and trust-state owner well. Three behavioral
contracts that cross independently built units are missing or underspecified,
and the known calendar-month rollover contradiction remains unsafe for FR-3
implementation. Pixel values, typography, and microcopy correctly remain owned
by the finalized UX artifacts rather than being repeated wholesale in the
architecture spine.

## Findings

### UX-R1 — HIGH — Boot/pending-time has no boundary representation

**Final UX contract:** the device boots into Clock view, shows best-effort time
once any Time source exists, and displays `UNSYNCED` until the first successful
NTP sync (`EXPERIENCE.md:23, 26, 57`).

**Current spine:** AD-3 requires every `TimeSnapshot` to contain a UTC instant and
local date/time fields, but it does not define whether `TimeService` can initially
have no usable wall-time, what it publishes in that state, or whether the app
delays rendering. AD-8 covers failures only while “the last wall-time keeps
advancing,” which does not cover a cold boot with no prior trustworthy instant.

**Divergence risk:** the time-service unit can return `None`, an arbitrary
power-on RTC date, or an unsynced snapshot, while the app and Clock renderer can
independently assume a concrete snapshot always exists. Those choices are not
interoperable.

**Required landing:** define one cross-boundary representation for
`pending/no-valid-wall-time` versus `unsynced-but-advancing`, and bind the app's
boot rendering behavior to it. Keep the visual treatment in UX; the spine only
needs to state what snapshot/state renderers receive and when Clock view begins.

### UX-R2 — HIGH — The shared `UNSYNCED` presentation contract is not enforced

**Final UX contract:** the badge is identical on both views, fixed top-right,
text-only `UNSYNCED`, present whenever trust is unsynced, absent with no reserved
space when synced, and the only orange element (`DESIGN.md:67, 86, 102, 106, 110`;
`EXPERIENCE.md:36, 39, 51, 58-59, 77`).

**Current spine:** AD-3 centralizes the trust value and the capability map names
both renderers, but no architecture rule prevents `clock_view.py` and
`calendar_view.py` from implementing separate badge geometry, visibility logic,
or palette usage.

**Divergence risk:** two independently built renderers can satisfy “show a badge”
yet disagree on position, label, spacing, or synced-state removal, violating the
explicit identical-on-both-surfaces contract.

**Required landing:** bind both views to one shared overlay/component or one
shared badge presentation contract sourced from configuration. The rule should
fix ownership and identical behavior, while `DESIGN.md` remains the authority for
exact colors, typography, and dimensions.

### UX-R3 — MEDIUM — The automatic-rotation state machine lost settled behavior

**Final UX contract:** Clock is the boot/default and primary view; it holds about
30 seconds, cuts to Calendar for about 5-10 seconds, returns to Clock, and repeats
indefinitely. The transition is a plain cut with no animation. No button, touch,
remote control, navigation affordance, or settings surface exists in v1
(`EXPERIENCE.md:15-17, 23-26, 66-70`).

**Current spine:** AD-2 names automatic view switching and AD-5 makes dwell
timing configurable, but neither fixes the initial state, two-state sequence,
plain-cut transition, or lack of input-triggered transitions. The capability map
only says “Clock-dominant auto-rotation.” The Structural Seed omits an input
adapter, which helps, but is seed rather than a behavior invariant.

**Divergence risk:** an app unit can boot to Calendar, animate transitions, add a
third state, or wait for an input signal while still nominally implementing an
automatic view switch.

**Required landing:** add a concise view-state contract: `Clock -> Calendar ->
Clock`, Clock initial, configured dwell values, timer-only transitions, plain
cut, repeat indefinitely. Exact dwell constants can remain configuration seed;
the UX ranges should be retained there rather than hard-coded in behavior.

### UX-R4 — HIGH FOR FR-3 — Month rollover remains contradictory and deferred

**Final UX statements:** the month grid's today highlight updates immediately at
local midnight on whichever view is visible (`EXPERIENCE.md:60`), while a month
rollover during an active Calendar dwell does not replace the grid until the next
Calendar entry (`EXPERIENCE.md:61`). For an end-of-month midnight, the old grid
contains no cell that can represent the new day's highlight, so both statements
cannot hold literally.

**Current spine:** Deferred explicitly identifies this conflict. That is an
accurate reconciliation; the spine did not silently invent an answer.

**Implementation impact:** the conflict is unsafe to leave unresolved when FR-3
interaction/rollover acceptance tests are authored. It affects app scheduling,
month-grid recomputation, and calendar rendering together.

**Required landing:** reconcile the UX source, then amend the existing Deferred
entry or add a stable rule without renumbering existing ADs. A coherent reading
would distinguish same-month midnight (update highlight immediately) from
end-of-month midnight (hold the old grid until next Calendar entry), but that is
a product/UX choice and must not be silently adopted by architecture.

## Correctly landed contracts

| UX contract | Spine coverage | Assessment |
| --- | --- | --- |
| Fixed 320 x 240 landscape hardware surface | Stack, hardware-doc ownership, diagram | Landed; controller identity remains correctly isolated as an assumption. |
| Local Vietnam date and midnight basis | AD-3, AD-4 | Landed. |
| Monday-first seven-column calendar with adjacent-month-capable cells | AD-6 | Landed; `in_month` plus Gregorian date supports overflow-day styling. |
| Both views consume one trust state | AD-3, capability map | Domain state landed; shared badge presentation still missing per UX-R2. |
| One-second updates without flicker or heap churn | AD-5, AD-7 | Landed at the cross-unit architecture level. |
| Palette values, sizes, fixed-width numerals, formats, no icons/seven-segment font | `src/config.py` ownership plus UX source | Correctly remains in `DESIGN.md`; no need to duplicate every visual token in the spine. |
| No theme/brightness system | Configuration convention and absence from seed | Adequately constrained by finalized UX; no competing subsystem is introduced. |
| Physical legibility requires panel verification | Deferred operational proof | Landed. |
| Hourly NTP retry and silent recovery | AD-5, AD-8 plus configured durations | Ownership landed; ensure the checked-in default preserves the finalized UX's hourly cadence. |

## Reconciliation gate

Before marking the spine final:

1. Specify the boot/pending-time boundary state (UX-R1).
2. Centralize or contractually share the badge presentation (UX-R2).
3. Fix the timer-only two-view state machine and plain-cut transition (UX-R3).
4. Resolve the end-of-month midnight contradiction with UX before FR-3 tests
   (UX-R4).

No other finalized UX detail needs promotion into an architecture decision.
