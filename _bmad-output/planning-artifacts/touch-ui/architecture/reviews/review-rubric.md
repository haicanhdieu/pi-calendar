# Review: Touch UI Architecture Spine vs. Good-Spine Checklist

Reviewed: `_bmad-output/planning-artifacts/touch-ui/architecture/ARCHITECTURE-SPINE.md`
Against: pico-w-calendar-clock spine (AD-1..AD-12), wifi-config spine (AD-1..AD-7),
touch-ui PRD/EXPERIENCE/DESIGN, and current code (`main.py`, `src/app.py`,
`src/ui/view_state.py`, `src/ui/compositor.py`, `src/ui/components.py`, `src/config.py`).

Overall verdict: **Conditional pass.** The spine correctly identifies most real
divergence points (network-status ownership, SPI0 CS handoff, dwell suspension,
shared idle timeout, Reboot as a Port) and its ADs are individually well-formed
and mostly enforceable in isolation. It has two internal consistency gaps that
would let two implementers diverge, one unresolved cross-document contradiction,
and one silent hardware dimension. None are fatal, but all should be closed
before "final" status is trusted for build.

---

## 1. Real divergence points fixed — mostly yes, with gaps

Fixed well:
- Network-status single-source-of-truth (AD-1) — correctly targets the actual
  bug in the current code: `src/ui/compositor.py::render()` unconditionally
  calls `draw_network_status_overlay` whenever `status` is non-`None`, and
  `src/app.py::_render()` always passes `status=self._network_status()`. AD-1's
  rule to stop calling it from the Clock/Calendar path is a real, checkable
  code change.
- SPI0 CS ownership (AD-3) — correctly generalizes the pattern already visible
  in `main.py` (which deselects `touch_cs` before TFT bring-up), preventing
  bus corruption between `Ili9341DisplayPort` and a new `TouchPort`.
- Reboot as a Port (AD-4) — mirrors the existing `ClockPort` pattern; enforceable
  and testable with a fake.
- Shared idle timeout (AD-8) — resolves the PRD's own 5-8s vs. UX's locked 15s
  conflict explicitly and correctly (follows the "locked Discovery decision").

Gaps (see §2-3 for detail):
- **Touch-input signal semantics (edge vs. level) are never decided.** AD-2
  only says `TouchPort.read()` "returns an immediate touch/no-touch result."
  Whether that result is a touch-down edge event or a level/contact-state read
  is left open, even though it materially changes both `touch_state.py`'s
  transition rule (AD-5) and the mandatory once-per-tap Press Flash (DESIGN.md:
  "shown only for the instant a tap registers... then gone"). Two
  implementations of `TouchPort`/`touch_state.py` could reasonably disagree
  here (e.g., a held finger continuously re-flashing vs. flashing once), which
  is exactly the class of divergence a spine at this altitude exists to close.
- **Ordering of the new touch step against AD-12's existing fixed loop order is
  unaddressed.** The inherited AD-12 (from the core spine) fixes a specific
  six-step order that `src/app.py::step()` already implements almost verbatim
  (steps 1, 1b, 2, 3, 4, 5-6 in the source). The touch-ui spine's AD-6 depends
  on `active_surface` already being current before step 4 ("handle view
  deadline") runs, but nowhere states where `TouchPort.read()` and the
  touch_state transition are evaluated relative to steps 1/1b (network event
  drain), 2 (snapshot), 3 (rollover), or 5-6 (render). This is a whole
  dimension AD-12 already made explicit for the parent spine and the child
  spine silently leaves open.

## 2. Every AD's Rule enforceable and actually prevents its divergence

Individually, each Rule (AD-1 through AD-8) is phrased as a specific,
checkable code constraint (named module, named method, named constant, or
explicit call-site removal) rather than a vague intention — that part of the
checklist item is satisfied AD-by-AD.

However, **AD-5 and AD-7 define two overlapping state dimensions for the same
concept ("Settings is open") without reconciling them**, which undermines the
enforceability of both:

- AD-5: "`AppState` gains `active_surface` and `surface_deadline` fields...
  Valid values: `rotation`, `bar`, `settings`."
- AD-7: "Settings is a third `active_view` value alongside `VIEW_CLOCK`/
  `VIEW_CALENDAR`, rendered through the same `compositor.render()` path."

That means entering Settings is modeled as *both* `active_surface = "settings"`
*and* `active_view = VIEW_SETTINGS` — two independent fields that must be kept
in lockstep by two different pieces of logic (`touch_state.py` per AD-5, and
whatever sets `active_view` per AD-7), with no rule stating which is
authoritative, whether they are set atomically in the same `App` method, or
what it means if they briefly disagree (e.g., mid-tick). The existing
`_render()` dispatch in `src/app.py` branches only on `active_view`
(`VIEW_CALENDAR` vs. else), and `_handle_view_deadline`/`_handle_rollover`
already read/write `active_view` for Rotation purposes only — folding a third
`active_view` value into that same field while *also* introducing a parallel
`active_surface` field is a live, unaddressed seam between AD-5 and AD-7. This
is the single clearest place the spine could let two units (the touch-surface
FSM and the render dispatch) diverge.

## 3. Nothing under Deferred could let two units diverge — mostly clean

Deferred items were checked individually:
- Touch debounce/palm-rejection, Bar slide animation pacing, touch controller
  identity, tap-target pixel sizes — all correctly deferred as single-owner
  implementation detail or explicitly-flagged unverified risk, not
  cross-module contracts. No divergence risk.
- **wifi-config AD-6 amendment** is the exception: this item defers the
  *actual edit* to a document that this spine explicitly says is now wrong.
  See §5 — this is a real problem, just filed under Deferred rather than
  Invariants.

## 4. Named tech verified-current

MicroPython 1.29.0 and the ILI9341-compatible/XPT2046-compatible assumptions
are carried over consistently from the parent spines and correctly flagged as
`[ASSUMPTION]` rather than asserted as fact. No new unverified tech claim is
introduced beyond what the core spine already carries. Acceptable.

## 5. Ratifies rather than contradicts brownfield — yes, with one loose thread

The spine's target-state changes to `compositor.py`/`app.py` are consistent
overwrites of code that already exists and is correctly described (verified
against the actual `render()`/`_render()`/`_network_status()` implementations
read above). `main.py` already holds `touch_cs` deselected during TFT
bring-up and already defines `TOUCH_CS`/`TOUCH_IRQ` in `config.py` — the spine
correctly builds on top of that groundwork rather than contradicting it.

The one real contradiction is **cross-document, not brownfield-code**: AD-1
explicitly overrides wifi-config spine's AD-6 display clause ("continuously
shows"/"at least 10 seconds"), but wifi-config's
`ARCHITECTURE-SPINE.md` on disk still contains the un-amended AD-6 text
verbatim (confirmed by reading that file). The touch-ui spine defers the
actual edit as "a follow-up action, not performed by this document." Until
that edit lands, the two canonical spine files disagree with each other, and
anyone reading the wifi-config spine alone (its own "Authority" section calls
it "the authoritative spine" for this exact concern) will get instructions
this newer spine says are wrong.

## 6. Spec coverage — binds FR-1..FR-6, UJ-1..UJ-3

All six FRs and three UJs are covered by the Capability → Architecture Map or
addressed by name in prose. One mapping gap: the **FR-4 row lists only AD-5,
AD-6, AD-7**, omitting **AD-1**, even though AD-1's rule ("read once, at the
moment the Settings view is entered") is specifically what implements FR-4's
"Network status line shown matches the Device's current connection state"
consequence. Low-severity but worth a one-line fix for traceability.

UJ-1 ("ambient glance, unchanged") has no explicit map row, but this is
acceptable — it is a non-change guaranteed implicitly by AD-6's rotation-only
dwell gate, and the checklist does not require a row for "nothing changed."

## 7. No new AD weakens or contradicts an inherited one

Checked against all of the core spine's AD-1, AD-2, AD-5, AD-7, AD-11, AD-12
and wifi-config's AD-1, AD-6 listed as inherited. No new AD here weakens
App's sole-writer status, the Port convention, `ticks_ms` scheduling, bounded
dirty-region rendering, or the DisplayPort contract — all are extended
consistently. The one deliberate override (AD-1 vs. wifi-config AD-6) is
correctly flagged as an override rather than silently ignored, which is the
right move procedurally — the gap is only that the target document is not
actually updated (§5).

## 8. Every dimension the altitude owns is decided/deferred/open — one silent gap

Nearly every operational dimension is addressed (SPI bus sharing, idle
timeout, touch boundary, reboot boundary, render path, Deferred list of
unresolved risks). One concrete hardware/operational dimension is left
completely silent:

- **`TOUCH_IRQ` (GP26)** is already defined in `src/config.py` ("2.8-inch TFT
  touch overlay... only its select and interrupt lines are unique") — strongly
  implying prior intent to use interrupt-driven touch detection. The spine's
  AD-2 commits instead to a purely polled `read()` once per `App.step()` and
  never mentions the IRQ pin at all — not in Invariants, Stack, or Deferred.
  It is unclear whether `TOUCH_IRQ` is (a) deliberately unused dead
  configuration, (b) meant to gate the SPI poll as a cheap "is anyone
  touching" pre-check, or (c) an oversight. Given it is a named, checked-in
  constant with an existing engineering comment about its purpose, this should
  at minimum be a one-line Deferred entry ("`TOUCH_IRQ` is unused in v1's
  polled design; revisit only if poll-rate SPI contention on shared SPI0
  becomes measurable") rather than silence.

---

## Findings summary (ranked)

| # | Severity | Finding |
|---|----------|---------|
| 1 | High | AD-5 (`active_surface` incl. `"settings"`) and AD-7 (`active_view` incl. a third `VIEW_SETTINGS` value) define two overlapping, unreconciled state dimensions for "Settings is open" — no rule states which is authoritative or how they stay in sync, risking divergence between `touch_state.py` and the render-dispatch code in `app.py`. |
| 2 | High | AD-2's `TouchPort.read()` contract never specifies touch-down-edge vs. level/contact-state semantics, even though this is load-bearing for both the once-per-tap Press Flash requirement (DESIGN.md) and `touch_state.py`'s idle/reveal transitions (AD-5) — a real per-tick behavioral divergence point left open. |
| 3 | Medium | The inherited AD-12 fixed loop order (already implemented near-verbatim in `src/app.py::step()`) is not amended to say where touch polling / surface-transition evaluation happens relative to network-event drain, rollover, and render — yet AD-6 depends on `active_surface` being current before the view-deadline step. |
| 4 | Medium | AD-1 declares wifi-config spine's AD-6 display clause overridden but defers the actual edit to that file as unscheduled follow-up; as of this review, `wifi-config/architecture/ARCHITECTURE-SPINE.md` AD-6 still reads "continuously shows... at least 10 seconds," leaving the two canonical spine documents contradicting each other on disk. |
| 5 | Low | `TOUCH_IRQ` (GP26), an existing checked-in config constant with an explicit hardware comment, is never mentioned by AD-2/AD-3/Stack/Deferred — a silent, unaddressed hardware dimension (used vs. intentionally dead). |
| 6 | Low | Capability → Architecture Map row for FR-4 omits AD-1, though AD-1's "read once at Settings entry" rule is what implements FR-4's status-matches-connection-state consequence. |

