# Epic 3 Context: Settings View with Network Status, Guideline, and Reboot

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Add the full-screen Settings view — a captured network-status snapshot, mode-branched guideline copy, and an immediate-fire Reboot control — as a third `active_view`, reachable only by tapping the gear icon on the revealed Bar and always exiting straight back to Rotation. This completes the two user journeys (reading connection info, recovering via reboot) the whole touch-UI effort exists for.

## Stories

- Story 3.1: Open Settings view from the gear icon with a captured status snapshot
- Story 3.2: Render status and mode-branched guideline copy
- Story 3.3: Reboot control with Press Flash, no confirmation
- Story 3.4: Settings idle timeout and outside-tap dismissal

## Requirements & Constraints

- Tapping the gear icon while the Bar is revealed transitions the device to Settings: Rotation is suspended entirely (not just paused), and the Bar is hidden. Clock/Calendar never draw underneath Settings.
- Settings shows the current network status branched by connection mode: Setup AP mode shows SSID + gateway; station mode shows the IPv4 address.
- Guideline copy is exact, two variants only: Setup AP — "Connect to Wi-Fi `<SSID>` then browse to `<gateway>`"; station — "Browse to http://`<ip>`". No punctuation flourish beyond this wording.
- Settings includes a Reboot button (label "REBOOT", all-caps, one word, no confirmation copy) absent from the Bar itself. Tapping it restarts the device immediately with no confirmation dialog and no second tap. No other Bar icon or Settings element ever triggers reboot.
- Settings is a static, non-scrolling, three-part read (status, guideline, action); nothing updates live while open.
- Settings returns to Rotation after the same shared idle timeout used by the Bar (`TOUCH_IDLE_TIMEOUT_MS = 15000`, not separately tunable) or immediately on a touch outside the Reboot button's tap target. There is no path from Settings back to Bar-Revealed — closing always returns straight to Rotation, resuming whichever view was showing, with its dwell deadline freshly re-armed from `now`.
- Tap feedback (Press Flash) is mandatory on the Reboot button (and gear icon) since the resistive touch panel may have inconsistent latency.
- Tap targets (gear icon, Reboot button) must be sized larger than their drawn glyph/text bounds for reliable fingertip contact.
- No back/close icon anywhere on Settings — idle timeout or outside tap are the only exits.

## Technical Decisions

- Settings is a third `active_view` value alongside `VIEW_CLOCK`/`VIEW_CALENDAR`, rendered through the existing `compositor.render()` path in `src/ui/settings_view.py` — not modeled as an overlay, since nothing draws underneath it (contrast with the Bar, which is a draw-last overlay, not a view).
- `AppState` gains `active_surface` (`rotation`/`bar`/`settings`), `surface_deadline`, and `settings_status_snapshot`; `App` alone commits these. On Settings entry, `App` copies the existing reduced `kind`/`ssid`/`ip` network state once into `settings_status_snapshot`; `settings_view.py` renders only that snapshot, never live state, and it is not refreshed again until the next Settings entry (this is what makes "captured at open" enforceable rather than incidental).
- `App.step()`'s step 0 (touch poll + hit-test via `touch_state.py`, committed before any other step) governs entry into Settings from a gear tap while Bar is revealed.
- While `active_surface == "settings"`, the existing view-dwell check (step 4, `next_view_after_dwell`) is skipped entirely — not deferred or accumulated. On return to `rotation`, the active view's dwell deadline is freshly re-armed from `now`.
- `surface_deadline` is set once on entry to `settings` and never renewed mid-surface; `touch_state.py` has no renew/reset-on-touch path (Settings has exactly one interactive target — Reboot — so every touch either hits it or is an outside tap, both of which transition away).
- Reboot crosses the hardware boundary via a new `src/device/reboot_port.py` `RebootPort` with a single `reset()` method; `main.py` backs it with `machine.reset()`, host tests inject a fake recording the call. `App` calls `reset()` synchronously on a Reboot tap.
- This epic overrides the wifi-config spine's AD-6 display clause ("continuously shows" / "at least 10 seconds"); that clause is dropped, keeping only its event-reduction rule. The UNSYNCED badge is unaffected by Settings and continues to draw per existing rules regardless of active view.
- Settings drawing goes exclusively through the existing `DisplayPort` contract (`fill_rect`/`draw_text`/`measure_text`, RGB565, stable font IDs) — no full 320x240x16 framebuffer redraw.
- All durations/rect sizes (idle timeout, tap-target sizes, Press Flash duration) are named constants in `src/config.py`; no touch or settings module embeds a literal duration or pixel rect.
- Tap-target rect helpers for the Reboot button live alongside the existing `badge_rect` helper in `src/ui/components.py`.

## UX & Interaction Patterns

- Layout, top-aligned and full-screen: 28px top padding, then the status line; 18px gap, then the guideline line; a larger gap, then the Reboot button positioned lower with clear separation, so Reboot reads as a distinct deliberate action rather than part of the informational block.
- Typography: Settings status is 16px bold, 1px letter-spacing, `digit-primary` (largest text on the view, since reading it is the point of opening Settings). Settings guideline is 13px regular, 0.5px letter-spacing, `digit-secondary`. Settings reboot label is 14px bold, 2px letter-spacing, all-caps, `digit-secondary` — same visual tier as the guideline, not louder; it's a normal control, not a warning.
- Color: Reboot button uses `digit-secondary` (amber) at rest, explicitly never `unsynced-bg` (red) — red stays reserved exclusively for the unsynced badge. `press-flash` (`#ffe9b8`, a brief tint of `digit-secondary`) shows only for the instant a tap registers on Reboot, then is gone; never a resting/hover color.
- No gestures beyond single tap anywhere — no swipe, long-press, or multi-touch. No dimming/scrim layer behind Settings; it is still a flat, single-layer display.
- Reference mockup: `_bmad-output/planning-artifacts/touch-ui/ux-designs/mockups/settings-view.html`.

## Cross-Story Dependencies

- Epic 3 depends on Epic 1 (TouchPort, RebootPort, `AppState` fields, `TOUCH_IDLE_TIMEOUT_MS`) and Epic 2 (`touch_state.py`, the Bar and its gear icon, `App.step()` step 0 wiring) already existing — Settings is reachable only via a gear tap on the revealed Bar.
- Story 3.1 (open Settings + snapshot capture) must land before 3.2 (status/guideline rendering), which depends on the snapshot shape; 3.3 (Reboot control) and 3.4 (timeout/outside-tap dismissal) both depend on 3.1's `active_surface == "settings"` transition and layout being in place.
- Story 3.4's outside-tap dismissal logic mirrors the Bar's outside-tap retraction from Story 2.3, and both share the same `TOUCH_IDLE_TIMEOUT_MS` constant from Epic 1 — no independent tuning.
