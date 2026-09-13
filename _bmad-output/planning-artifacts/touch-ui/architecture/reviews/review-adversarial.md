---
name: Adversarial Review — Touch UI Architecture Spine
type: review
target: ../ARCHITECTURE-SPINE.md
method: two-implementer divergence (construct pairs of AD-literal units that build incompatibly)
created: 2026-09-13
---

# Adversarial Review — Touch UI Architecture Spine

**Verdict:** The spine is well-constructed for its named hazards (SPI0 handoff, single-writer state, port boundaries) but leaves at least five AD-literal forks open — the sharpest being that AD-1's "captured at Settings entry" rule and AD-7's "Settings renders through the same `compositor.render()` path" rule pull toward two different, both-compliant data flows for the exact same status payload, one of which silently violates the UX spec's no-live-update requirement.

Method: for each finding, "Engineer A" and "Engineer B" independently implement the spine, each reading every AD literally and satisfying it, producing incompatible code one level down (module shapes, call sites, or field semantics).

---

## Finding 1 — AD-1 vs AD-7: no field exists to hold the "captured at entry" status snapshot

**Severity: HIGH**

AD-1's rule: network status is "read once, at the moment the Settings view is entered." The UX spec (EXPERIENCE.md) is explicit that Settings "doesn't live-update... reflecting the network state at time of entry."

AD-7's rule: "Settings is a third `active_view` value... rendered through the same `compositor.render()` path" as Clock/Calendar.

The Structural Seed's only new `AppState` fields are `active_surface` and `surface_deadline` (AD-5). No captured-status field is declared anywhere in the spine.

- **Engineer A** reads AD-1 literally: on the `rotation/bar → settings` transition, App copies `self._network_status()`'s current dict into a new field (e.g. `self._settings_status`) once, and `App._render()` passes that frozen dict as `status=` only when rendering the Settings view — Clock/Calendar continue to get `status=None` (per AD-1's overlay-removal clause).
- **Engineer B** reads AD-7 literally: Settings is "just another `active_view`," rendered through the exact same `compositor.render(view, snapshot, status=...)` call already used for Clock/Calendar, which today always passes `self._network_status()` — the *live*, continuously-mutated `_overlay_kind/_overlay_ssid/_overlay_ip` fields the network-event drain (`App.step()` §1b) updates every tick. Nothing in AD-7's text tells Engineer B to special-case Settings' `status=` argument, since "same path" is the whole point of the rule.

Both implementations satisfy their governing AD to the letter. Engineer A's Settings view is frozen at entry (matches UX spec); Engineer B's silently live-updates if a `NetworkEvent` (e.g. Setup→station-online) lands while Settings happens to be open — the exact bug the UX spec flags as an edge case to avoid. The spine gives no tie-breaker: it never states that Settings' `status=` argument must be a value distinct from, and decoupled from, the one Clock/Calendar receive.

**Close with:** an AD (or a tightened AD-1) that names the field — e.g. "`App` maintains `_settings_status_snapshot`, written exactly once on the `rotation/bar → settings` transition from the then-current `self._network_status()`, and `compositor.render()` for `VIEW_SETTINGS` is always called with that frozen value, never with a fresh `self._network_status()` call" — and states that this snapshot is *not* AppState (App already owns replacing it per AD-2, but it should not silently participate in the badge/network `_prev_*` invalidate-tracking `UiCompositor` uses for live status).

---

## Finding 2 — AD-7 vs inherited AD-12: no single required call site for Bar drawing

**Severity: HIGH**

Inherited AD-12: "`UiCompositor` stays the sole status/overlay draw-last owner; touch UI composes through it." AD-7: "Bar renders as a compositor-drawn overlay component... after the frozen base view, analogous to the existing UNSYNCED badge."

`UiCompositor.render()` today has signature `render(self, base_view, snapshot, *args, status=None)` and owns `_prev_badge`/`_prev_network_key` so it can invalidate the base view exactly when badge/network visibility changes before redrawing — a bookkeeping pattern nothing in AD-7 assigns to Bar.

- **Engineer A** adds a `bar=` kwarg to `UiCompositor.render()`, mirroring the existing `_prev_badge` pattern with a new `_prev_bar_visible`, so Bar visibility changes correctly invalidate the frozen base view before the strip is drawn/erased. One call site, one owner, matches AD-12's "sole... owner" language.
- **Engineer B** also satisfies AD-12 and AD-7 to the letter by treating "touch UI composes through it" as "the touch UI *module* is reached via the `UiCompositor` object," not "the draw call must live inside `render()`'s body." `App._render()` calls `self._compositor.render(...)` for the base view exactly as today, then separately calls a new `self._compositor.draw_bar_overlay(bar_state)` method immediately after — still "through `UiCompositor`," still "after the frozen base view," still nominally draw-last.

Engineer B's shape is a real, silent bug relative to Engineer A's: because Bar's appearance/disappearance never runs through the `_prev_badge`-style invalidate-before-redraw bookkeeping, transitioning out of Bar (idle timeout / outside tap) can leave the Bar strip's pixels behind if the next frame's `force_redraw` logic doesn't happen to already cover that region — the same stale-pixel class of bug AD-12's invalidate pattern exists to prevent for the badge. Both engineers can point to the same AD text as justification for their (incompatible, differently-safe) call-site choice.

**Close with:** an AD amendment naming the exact call surface — "Bar visibility is tracked as `_prev_bar_visible` state *inside* `UiCompositor`, using the identical invalidate-before-redraw pattern as `_prev_badge`; `UiCompositor.render()` gains the only sanctioned Bar-drawing code path; no second `draw_*` method on `UiCompositor` or `App._render()` may independently emit Bar pixels."

---

## Finding 3 — AD-2's "position optional" leaves the Bar-strip-but-not-gear tap undefined, with divergent TouchPort capability as the fork point

**Severity: MEDIUM-HIGH**

EXPERIENCE.md's Bar-Revealed row gives exactly two touch-driven exits: "tap gear → Settings" and "outside-Bar tap → Rotation," plus idle timeout. It never states what a touch that lands *inside* the 36px bar strip but *not* on the gear's tap-target should do.

AD-2: `TouchPort.read()` "returns an immediate touch/no-touch result (position optional — v1 needs only 'a touch occurred' and, for Bar, whether it landed on the gear's tap-target rect)." AD-5: `touch_state.py` is "functions taking an explicit current surface value plus a touch/timeout/tap-target input" — no third tap-target category (bar-blank) is named.

- **Engineer A** builds `TouchPort` with only the two bits AD-2 requires literally — `touched: bool`, `on_gear: bool` — nothing else. In `touch_state.py`, any touch that is not `on_gear` is indistinguishable from an outside tap, so it necessarily reduces to `rotation` (Bar dismissed). Tapping the blank part of the bar strip bounces the user straight back to Rotation.
- **Engineer B**, reading the same AD-2 text, decides "position optional" only means *precise coordinates* are optional, not that a second rect test is disallowed, and adds `on_bar: bool` to `TouchPort`'s result so `touch_state.py` can treat "on bar, not on gear" as a no-op that merely keeps `bar` active (and, per the UX's "no touch activity" idle language, arguably should reset `surface_deadline`). Tapping the blank part of the bar strip does nothing and does not dismiss Bar.

Both TouchPort shapes satisfy AD-2's letter ("position optional... for Bar, whether it landed on the gear's tap-target rect" — that's a floor, not a ceiling, so B's extra bit isn't forbidden). The resulting UX — and the `touch_state.py` function signatures each engineer builds — are incompatible: A's takes a 2-value tap-target enum (`gear`/`outside`), B's takes a 3-value one (`gear`/`bar-blank`/`outside`). A component built against A's signature cannot be tested or reused against B's.

**Close with:** the spine must enumerate the tap-target categories `touch_state.py` accepts (e.g. `TAP_GEAR`, `TAP_REBOOT`, `TAP_OUTSIDE` — and explicitly state whether "on bar strip but not on gear" is folded into `TAP_OUTSIDE` or is a distinct no-op category), and pin `TouchPort`'s result shape to carry exactly the bits needed to compute that category, no more, no less.

---

## Finding 4 — AD-8 doesn't state whether `surface_deadline` is a sliding idle timer or a fixed one-shot deadline

**Severity: MEDIUM**

AD-8: "`src/config.py` defines a single `TOUCH_IDLE_TIMEOUT_MS = 15000`, used identically by Bar-Revealed and Settings." This pins the *value*, not the *update rule* for the field that consumes it (`surface_deadline`, introduced by AD-5). The UX spec's framing — "no touch activity for 15s... automatic return to Rotation" — describes a sliding/renewing timer, but no AD states that `surface_deadline` must be recomputed as `now + TOUCH_IDLE_TIMEOUT_MS` on every touch processed while `active_surface != "rotation"`, as opposed to being computed once on entry and never touched again until the surface changes.

Given Finding 3's ambiguity, this compounds: if Engineer B's `TAP_OUTSIDE`/blank-bar no-op path exists, whether that no-op renews `surface_deadline` is exactly the kind of divergence AD-8 fails to close — Engineer A (no renewal) ejects the user to Rotation after a flat 15s regardless of interaction; Engineer B (renewal on every processed touch) keeps Bar open indefinitely under repeated blank-area taps. Both read `TOUCH_IDLE_TIMEOUT_MS` "identically."

**Close with:** state explicitly in AD-6 or AD-8 that `surface_deadline` is recomputed as `now + TOUCH_IDLE_TIMEOUT_MS` on (a) the transition into `bar`/`settings`, and (b) every subsequent touch event processed while `active_surface != "rotation"` that does not itself cause a transition — i.e. name it as a renewing idle timer, not a one-shot deadline, and make that the single source of truth `App.step()` reads.

---

## Finding 5 — App.step()'s existing numbered event order does not pin the touch-read insertion point, and the two plausible insertions produce different same-tick semantics

**Severity: HIGH**

Current `src/app.py` `App.step()` docstring: "Loop order (AD-12): adapter results → network events → snapshot → rollover → view deadline → base render → status layer," implemented as steps `1` (consume adapter results / maybe enqueue sync), `1b` (drain `NetworkEvent`s into overlay state), `2` (derive snapshot), `3` (rollover), `4` (view deadline / dwell), `5–6` (render). **The new spine does not amend this order.** AD-2 only says `TouchPort.read()` is "called once per `App.step()`" — it does not say where in the six-step sequence.

This is not cosmetic — it changes observable behavior in the same tick a Bar/Settings transition coincides with a network event:

- **Engineer A** inserts touch handling as a new step **0**, before adapter/network draining: `touch = self._touch.read(); self.state.active_surface = touch_state.next_surface(...)`. If a `NetworkEvent` (e.g. Setup-AP → station-online, carrying a fresh IP) is *also* pending this same tick, and the touch transition happens to be the `bar → settings` entry, Finding 1's captured-status snapshot (however it's implemented) is taken from `self._network_status()` **before** step 1b drains the new event — Settings opens showing the *stale* pre-event network status for one tick's worth of staleness, then never updates (by AD-1's own "doesn't live-update" rule) even though fresher data was already sitting in the mailbox/queue when Settings opened.
- **Engineer B** inserts touch handling **after** step 1b (network drain) but **before** step 2 (snapshot), reading AD-2's "once per step" equally literally. In the identical scenario, the same-tick `bar → settings` entry captures the network status **after** the drain — Settings opens already showing the fresh IP.

Both orderings satisfy AD-2's "once per `App.step()`" to the letter; they are not observably different for touch/bar mechanics alone, but they produce different, silently-diverging answers to "what network status does Settings show" in the one-tick race the spine's own AD-1 rule ("captured at the moment... entered") depends on being well-defined. Because `App.step()`'s docstring is treated as normative elsewhere in this codebase (it's literally cited as "AD-12" in the existing source), a future maintainer has no textual signal that touch insertion is *supposed* to be pinned by the new spine and may reasonably assume either ordering is a "detail."

This finding also covers the prompt's AD-3 sub-question: AD-3's CS-handoff rule already makes bus corruption impossible regardless of where `TouchPort.read()` is inserted (every read fully deselects/reselects around itself), so ordering is *not* a bus-safety hazard — but it is an unpinned same-tick event-ordering hazard the spine doesn't close, and the "SPI0 mid-transfer" framing in the prompt is really this event-ordering gap in different clothing.

**Close with:** amend `App.step()`'s AD-12 loop-order docstring (and add a numbered spine AD, since this crosses into new touch territory) to state exactly where `TouchPort.read()` / `touch_state.py` evaluation sits relative to steps 1b/2/4 — recommend directly after step 1b (network drain) and before step 2 (snapshot), so any same-tick Settings-entry capture in Finding 1 always sees post-drain network state, and the AD-6 dwell-suspension check in step 4 always sees the current tick's `active_surface`, not last tick's.

---

## Secondary observations (not full findings)

- **AD-6 "resumes from the view it was showing" vs the rollover path (`_handle_rollover`).** If a month/day rollover happens while `active_surface` is `bar`/`settings` (base view frozen, dwell suspended per AD-6), the existing `_handle_rollover` still runs every tick (it's not gated by `active_surface` in the current `App.step()`, and nothing in the new spine says it should be) and may force `active_view` from Calendar back to Clock mid-Bar/Settings. Whether "the view it was showing" (AD-6) is captured *before* or *after* such a forced rollover, and whether the frozen base view should even be allowed to silently swap under the user's feet while Bar/Settings sits on top of it, is unaddressed. Likely benign in practice (rollover is date-boundary-rare) but worth a one-line rule.
- **Deferred section vs AD-2's "once per step."** The Deferred note on Bar slide animation ("incremental `fill_rect` steps... on a tighter animation sub-tick") already anticipates a rendering cadence faster than `App.step()`'s tick; if that sub-tick loop is ever implemented as a nested loop rather than deferred to future `step()` calls, it would need its own touch-read policy that AD-2's "once per `App.step()`" doesn't obviously cover. The spine already flags this as unresolved/deferred, so it is not scored as a new finding, but Finding 5's fix should note the interaction so the two aren't closed independently and re-diverge later.

---

## Summary table

| # | Finding | Severity | ADs in tension |
| --- | --- | --- | --- |
| 1 | No field for Settings' captured-at-entry status snapshot | HIGH | AD-1 vs AD-7 |
| 2 | No single required call site for Bar drawing inside UiCompositor | HIGH | AD-7 vs AD-12 (inherited) |
| 3 | Bar-strip-but-not-gear tap category undefined; TouchPort capability forks `touch_state.py`'s signature | MEDIUM-HIGH | AD-2 vs AD-5 |
| 4 | `surface_deadline` renewal rule (sliding vs one-shot) unstated | MEDIUM | AD-6 vs AD-8 |
| 5 | Touch-read insertion point in `App.step()` unpinned; races Finding 1's snapshot capture | HIGH | AD-2/AD-3 vs App.step()'s existing (unamended) event order |
