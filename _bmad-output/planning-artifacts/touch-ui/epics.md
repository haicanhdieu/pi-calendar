---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - _bmad-output/planning-artifacts/touch-ui/prds/prd.md
  - _bmad-output/planning-artifacts/touch-ui/architecture/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/touch-ui/ux-designs/DESIGN.md
  - _bmad-output/planning-artifacts/touch-ui/ux-designs/EXPERIENCE.md
---

# touch-ui - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for touch-ui, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: Device does not render the Network status line on the Clock view or Calendar view during Rotation. Neither Setup AP (SSID+gateway) nor station IP text appears anywhere during normal Rotation. UNSYNCED badge unaffected.

FR-2: While Device is in Rotation, any touch on the screen transitions it to Bar-Revealed: Rotation pauses, Bar slides up from bottom edge over ~200-300ms. Bar renders as an icon-list container (not hardcoded single button). While Bar-Revealed, Rotation's view-switch timer does not fire.

FR-3: Bar-Revealed returns to Rotation after Idle timeout (shared constant, 15s) with no touch, or immediately on touch outside the Bar's own area. Touch on the Settings icon opens Settings instead of retracting.

FR-4: Tapping the Settings icon while Bar-Revealed transitions Device to Settings, suspending Rotation entirely (Bar also hidden). Settings renders full-screen; Clock/Calendar do not draw underneath. Network status line matches current connection state (Setup AP: SSID+gateway; station: IPv4). Guideline line worded per same branch ("Connect to Wi-Fi `<SSID>` then browse to `<gateway>`" / "Browse to http://`<ip>`").

FR-5: Settings view includes a Reboot button, absent from the Bar itself. Tapping Reboot restarts the Device (soft reset) immediately, no confirmation dialog. No other Bar icon triggers reboot, now or later.

FR-6: Settings view returns to Rotation after Idle timeout (5-8s per PRD, locked to shared 15s constant per UX) with no touch activity, same mechanism as Bar. Timeout duration is shared with the Bar's (single configured constant), not separately tunable.

### NonFunctional Requirements

NFR-1: Bar reveal/retract animation must not visibly stutter or blank the screen mid-transition (~200-300ms slide, bounded dirty-region draws, no full-framebuffer redraw).

NFR-2: Touch reads must not corrupt in-flight SPI0 TFT transfers — touch and display share the SPI0 bus and must be handed off safely on every touch read.

NFR-3: Tap feedback (Press Flash) is mandatory on every interactive element (gear icon, Reboot button) since the resistive touch panel may have inconsistent response latency; a tap with no visible acknowledgment reads as broken hardware.

NFR-4: Tap targets (gear icon, Reboot button) must be sized for reliable fingertip contact, larger than their drawn glyph/text bounds.

### Additional Requirements

- New `src/ui/touch_state.py`: pure module, no device imports, mirrors `view_state.py` shape; decides `rotation` / `bar` / `settings` transitions from current surface + touch/timeout/tap-target input.
- New `src/device/touch_port.py`: `TouchPort` with single synchronous `read()` returning `(edge_down, x, y)` on touch-down edge only (not raw contact level); performs internal outlier/noise rejection; called once per `App.step()`.
- `TouchPort` alone owns the SPI0 TFT/touch handoff: deselect `tft_cs`, select `touch_cs`, drop baudrate to XPT2046-safe rate (≤2MHz), transfer, restore `config.SPI_BAUDRATE`, deselect `touch_cs`, reselect `tft_cs`. `Ili9341DisplayPort` stays unaware a touch peripheral exists.
- New `src/device/reboot_port.py`: `RebootPort` with single `reset()` method; `main.py` backs it with `machine.reset()`; host tests inject a fake recording the call.
- `AppState` gains `active_surface`, `surface_deadline`, and `settings_status_snapshot` fields; `App` alone commits their replacement.
- `App.step()` gains new step 0 (before existing step 1 `_consume_sync_result`/`_maybe_enqueue_sync`): poll `TouchPort.read()`, hit-test any `edge_down` touch via `touch_state.py` against current `active_surface`, commit resulting `active_surface`/`surface_deadline` (and, on Settings entry, the status snapshot) before any other step runs.
- `App.step()`'s existing view-dwell check (step 4, `next_view_after_dwell`) runs only when `active_surface == "rotation"`; skipped entirely (not deferred/accumulated) while `bar` or `settings` is active. On return to `rotation`, the active view's dwell deadline is freshly re-armed from `now`.
- `App`/`UiCompositor` stop calling `draw_network_status_overlay` from the Clock/Calendar base-view render path in every `NetworkCoordinator` mode (including Setup-AP). On Settings entry, `App` copies the existing reduced `kind`/`ssid`/`ip` state once into `AppState.settings_status_snapshot`; `settings_view.py` renders only that snapshot (never live state), and it is not updated again until the next Settings entry.
- This overrides wifi-config spine's AD-6 display clause ("continuously shows" / "at least 10 seconds"); that spine's AD-6 must be updated by this work to drop the display rule while keeping the event-reduction rule.
- New `src/ui/settings_view.py`: renders Settings as a third `active_view` value alongside `VIEW_CLOCK`/`VIEW_CALENDAR`, through the existing `compositor.render()` path.
- `src/ui/compositor.py`: Bar renders as a compositor-drawn overlay component (bar strip + gear glyph + press-flash) after the frozen base view, analogous to the existing UNSYNCED badge — never modeled as an `active_view`. Exactly one Bar draw call site, inside `UiCompositor.render()`. `UiCompositor` invalidates the Bar's prior draw region the same way it invalidates on badge visibility change.
- `src/ui/components.py`: add `bar_rect`/gear tap-target rect/Reboot tap-target rect helpers, alongside the existing `badge_rect` helper; tap-target rects sized larger than drawn glyph/text bounds per Accessibility Floor.
- `src/config.py`: add `TOUCH_IDLE_TIMEOUT_MS = 15000` (single named constant shared by Bar and Settings, overriding PRD's stated 5-8s range per UX Discovery decision), bar slide duration/frame-pacing constants, tap-target rect size constants, Press Flash duration constant — no touch module embeds a literal duration or pixel rect.
- `surface_deadline` is set once on entry to `bar` or `settings` and never renewed mid-surface (every touch while active either hits the one interactive target, transitioning away, or lands outside it, transitioning away immediately) — `touch_state.py` must not implement a renew/reset-on-touch path.
- All Bar/Settings drawing goes exclusively through the existing `DisplayPort` contract (`fill_rect`/`draw_text`/`measure_text`, RGB565, stable font IDs); no full 320x240x16 framebuffer redraw.
- Reboot fires immediately on tap with no confirmation step (per locked UX decision).
- Rotation resumes from whichever view was showing when Bar/Settings closed, rather than restarting its cycle (resolves PRD Open Question #2).
- Touch debounce / palm-rejection hardening is explicitly deferred/out of scope for this epic set (flagged as an owner-less open risk, not designed here).
- `TOUCH_IRQ` (GP26) is wired and named in `config.py` but left unused; poll-only design via `TouchPort.read()` per `App.step()`.

### UX Design Requirements

UX-DR1: Amend base DESIGN.md rule "Don't introduce any icon set" to "No icon set beyond what Settings needs" — exactly one gear glyph, solid filled silhouette (8 teeth, punched center hole), 0px corner rounding, no sun/radiating-spoke or soft/rounded variant.

UX-DR2: Add new token/color `bar-panel-bg` (#141414) as the only new "surface" color — a flat color swap (no shadow/elevation/scrim), a hair lighter than base `bg` (#0a0a0a), used solely for the Bar strip.

UX-DR3: Add new token/color `press-flash` (#ffe9b8) — a brief tint of `digit-secondary`, shown only for the instant a tap registers on the gear icon or Reboot button, then gone; never a resting/hover color.

UX-DR4: Reboot button uses `digit-secondary` (amber) at rest, explicitly not `unsynced-bg` (red) — red stays reserved exclusively for the unsynced badge.

UX-DR5: Add three new typography roles for full-screen legibility: Settings status (16px bold, 1px letter-spacing, `digit-primary`), Settings guideline (13px regular, 0.5px letter-spacing, `digit-secondary`), Settings reboot (14px bold, 2px letter-spacing, all-caps "REBOOT", `digit-secondary`).

UX-DR6: Touch Bar layout — bottom-docked strip, 36px tall (~15% of 240px frame height), full width, `bar-panel-bg`, slides up from bottom edge over 200-300ms; gear icon centered in strip; Clock/Calendar view above is completely unaffected (no resize/dim/scrim) while Bar docks over its bottom edge.

UX-DR7: Settings view layout — full-screen, replaces Clock/Calendar entirely while open, stacked and top-aligned: 28px top padding then status line; 18px gap then guideline line; larger gap below guideline then Reboot button positioned lower with clear separation, so Reboot reads as a distinct deliberate action.

UX-DR8: No back/close icon anywhere on Bar or Settings — the only exits are idle timeout or an outside tap (tap-target-minimalism).

UX-DR9: Give every tap target (gear icon, Reboot button) a Press Flash — mandatory immediate visual acknowledgment for a resistive/XPT2046 touch panel with inconsistent latency.

UX-DR10: Gear icon and Reboot button both get generous tap targets sized for a fingertip, distinct from (larger than) their visible glyph/text render size.

UX-DR11: Two copy strings only, exact wording, no punctuation flourish: Guideline line Setup AP mode "Connect to Wi-Fi `<SSID>` then browse to `<gateway>`"; Guideline line station mode "Browse to http://`<ip>`". Button label "REBOOT" — all-caps, one word, no verb-phrase softening, no confirmation copy.

UX-DR12: Settings view is a static, non-scrolling, three-part read (status, guideline, action); nothing updates live while open — status reflects network state captured at the moment Settings opens, not a live-refreshing panel.

UX-DR13: No gestures beyond single tap anywhere in this spine — no swipe, no long-press, no multi-touch.

UX-DR14: Retract (Bar) — touch outside the Bar's own area (not on gear icon) retracts immediately, no animation delay beyond reverse of reveal slide. Retract (Settings) — touch outside the Reboot button's tap target closes Settings immediately, same treatment.

### FR Coverage Map

FR-1: Epic 1 - remove always-on network status overlay from Rotation
FR-2: Epic 2 - reveal Bar on any touch during Rotation
FR-3: Epic 2 - Bar auto-retracts on idle timeout or outside tap
FR-4: Epic 3 - open full-screen Settings view from the gear icon
FR-5: Epic 3 - Reboot control, immediate, no confirmation
FR-6: Epic 3 - Settings shares Bar's idle timeout
NFR-1: Epic 2 - stutter-free bounded-dirty-region Bar animation
NFR-2: Epic 1 - safe SPI0 handoff between TouchPort and display
NFR-3: Epic 2, Epic 3 - mandatory Press Flash tap feedback
NFR-4: Epic 1, Epic 3 - fingertip-generous tap-target rects
UX-DR1, UX-DR6, UX-DR9, UX-DR10, UX-DR14: Epic 2 - Bar visual identity and touch feedback
UX-DR2, UX-DR3, UX-DR4, UX-DR5, UX-DR7, UX-DR11, UX-DR12: Epic 3 - Settings visual identity and copy
UX-DR8, UX-DR13: Epic 2, Epic 3 - no back/close icon, single-tap-only interaction

## Epic List

### Epic 1: Remove Always-On Status, Stand Up Touch Hardware Ports
Removes the permanent network-status overlay from the ambient Rotation view and gives the Device safe, testable hardware boundaries (TouchPort, RebootPort) — a complete, shippable cleanup on its own even before any touch interaction exists.
**FRs covered:** FR-1 (NFR-2, NFR-4 supporting)

### Epic 2: Touch-Reveal Bar
Lets Minh touch the screen to reveal a bottom Bar with a gear icon, which reliably auto-retracts — a complete, standalone touch interaction even before Settings exists behind it.
**FRs covered:** FR-2, FR-3 (NFR-1, NFR-3 supporting)

### Epic 3: Settings View with Network Status and Reboot
Lets Minh tap the gear to see his Device's network info and reboot it — completing the two user journeys (UJ-2, UJ-3) the whole PRD exists for.
**FRs covered:** FR-4, FR-5, FR-6 (NFR-3, NFR-4 supporting)

## Epic 1: Remove Always-On Network Status, Add Touch Hardware Ports

Strip the always-on network status overlay from Rotation and stand up the hardware boundary (TouchPort, RebootPort) and AppState fields the rest of the touch UI depends on, without yet exposing any touch interaction.

### Story 1.1: Remove always-on network status overlay from Rotation

As Minh,
I want the Clock and Calendar views to stop showing the network status line during normal rotation,
So that the screen only shows time/date info unless I explicitly ask for network details.

**Acceptance Criteria:**

**Given** the Device is in Rotation, in any `NetworkCoordinator` mode (Setup AP or station),
**When** the Clock view or Calendar view renders,
**Then** no Setup AP SSID+gateway text and no station IP text appears anywhere on screen.
**And** the existing UNSYNCED badge continues to render unaffected, exactly as before.
**And** `App`/`UiCompositor` no longer call `draw_network_status_overlay` from the Clock/Calendar base-view render path in any mode.
**And** the `kind`/`ssid`/`ip` state `App` already reduces from `NetworkEvent`s is retained unchanged internally (only the draw call is removed, not the state).

### Story 1.2: Add TouchPort and RebootPort hardware adapters

As the implementer,
I want TouchPort and RebootPort as minimal, testable hardware boundary objects,
So that touch reads and reboot are polled/synchronous like existing ports and safely share the SPI0 bus with the display.

**Acceptance Criteria:**

**Given** `src/device/touch_port.py` is added,
**When** `TouchPort.read()` is called once per `App.step()`,
**Then** it returns `(edge_down: bool, x: int | None, y: int | None)`, with `edge_down` true only on the first read where contact is present after a prior no-contact read.
**And** repeated reads during a held/lingering touch report `edge_down=False` until release and a new contact.
**And** internally `read()` performs outlier/noise rejection across multiple raw ADC samples before returning, without introducing any async machinery, queue, or mailbox.

**Given** a call to `TouchPort.read()`,
**When** it performs its SPI transfer,
**Then** it deselects `tft_cs`, selects `touch_cs`, drops SPI0's baudrate to the XPT2046-safe rate (≤2MHz), performs the transfer, restores SPI0 to `config.SPI_BAUDRATE`, deselects `touch_cs`, and reselects `tft_cs`.
**And** `Ili9341DisplayPort` contains no reference to `touch_cs` and remains unaware a touch peripheral exists.

**Given** `src/device/reboot_port.py` is added,
**When** `RebootPort.reset()` is called,
**Then** `main.py`'s concrete implementation calls `machine.reset()`.
**And** a fake `RebootPort` used in host tests records the call instead of executing it.

**Given** `AppState` in `src/app.py`,
**When** the touch UI is added,
**Then** it gains `active_surface` (values `rotation`/`bar`/`settings`), `surface_deadline`, and `settings_status_snapshot` fields, all committed exclusively by `App`.
**And** `src/config.py` gains `TOUCH_IDLE_TIMEOUT_MS = 15000` as a single named constant, plus named constants for bar slide duration/frame pacing, tap-target rect sizes, and Press Flash duration — no touch module embeds a literal duration or pixel rect.

## Epic 2: Touch-Reveal Bar with Reveal/Retract State Machine

Implement the pure `touch_state.py` transition logic and wire it into `App.step()` so any touch during Rotation reveals a bottom-docked Bar with a gear icon, which auto-retracts on idle timeout or an outside tap.

### Story 2.1: Pure touch_state transitions for rotation ⇄ bar

As the implementer,
I want a pure, device-import-free `touch_state.py` module governing rotation/bar/settings transitions,
So that surface decisions are unit-testable and have exactly one owner.

**Acceptance Criteria:**

**Given** `src/ui/touch_state.py` is added, mirroring `view_state.py`'s shape,
**When** the current surface is `rotation` and an `edge_down` touch occurs anywhere on screen,
**Then** the function returns `bar` as the next surface, alongside a freshly-set `surface_deadline` of `now + TOUCH_IDLE_TIMEOUT_MS`.
**And** the module contains no device/hardware imports.

**Given** the current surface is `bar`,
**When** `TOUCH_IDLE_TIMEOUT_MS` elapses with no further `edge_down` touch,
**Then** the function returns `rotation` as the next surface.
**And** `surface_deadline` is set once on entry to `bar` and never renewed mid-surface — no renew/reset-on-touch path exists in the module.

**Given** `src/config.py`'s new named constants (bar height, slide duration, tap-target sizes),
**When** the Bar strip and gear icon are drawn,
**Then** no touch or drawing module embeds a literal duration or pixel rect inline.

### Story 2.2: Wire touch polling into App.step() and render the Bar overlay

As Minh,
I want any touch on the screen during Rotation to reveal a bottom Bar with a gear icon within one animation cycle,
So that I can reach Settings without the Bar being permanently visible.

**Acceptance Criteria:**

**Given** `App.step()`'s existing numbered event order,
**When** a new step 0 is added before the existing step 1 (`_consume_sync_result`/`_maybe_enqueue_sync`),
**Then** it calls `TouchPort.read()`, hit-tests any `edge_down` touch through `touch_state.py` against the current `active_surface`, and commits the resulting `active_surface`/`surface_deadline` before any other step in that tick runs.

**Given** the Device is in Rotation and the user touches the screen anywhere,
**When** the next `App.step()` runs,
**Then** the Bar slides up from the bottom edge over 200-300ms, rendered via `fill_rect` incremental steps (bounded dirty regions, no full-framebuffer redraw), with no visible stutter or screen blanking mid-transition.
**And** the Bar renders as an icon-list container (not a single hardcoded button) — the gear icon centered in a 36px-tall, full-width, `bar-panel-bg` (#141414) strip.
**And** the underlying Clock/Calendar view continues rendering unaffected (no resize, dim, or scrim) while the Bar docks over its bottom edge.
**And** while `active_surface == "bar"`, `App.step()`'s existing view-dwell check (step 4, `next_view_after_dwell`) is skipped entirely, not deferred or accumulated.
**And** `UiCompositor` invalidates the Bar's own prior draw region the same way it already invalidates on badge visibility change, and the Bar has exactly one draw call site inside `UiCompositor.render()`.

**Given** the gear icon is drawn,
**When** the user's finger touches down on it,
**Then** a Press Flash (`#ffe9b8`) shows briefly on the glyph before any resulting transition, using a tap-target rect sized larger than the drawn glyph's visible bounds.

### Story 2.3: Auto-retract Bar on idle timeout or outside tap

As Minh,
I want the Bar to disappear on its own if I don't use it, or immediately if I tap elsewhere,
So that the screen returns to its ambient, chrome-free resting state without extra effort.

**Acceptance Criteria:**

**Given** the Bar is revealed with no further touch activity,
**When** `TOUCH_IDLE_TIMEOUT_MS` (15s) elapses,
**Then** the Bar retracts and `active_surface` returns to `rotation`, with the previously active Clock/Calendar view's dwell deadline freshly re-armed from `now`.

**Given** the Bar is revealed,
**When** a touch lands outside the Bar's own area (not on the gear icon),
**Then** the Bar retracts immediately, with no animation delay beyond the reverse of the reveal slide, and `active_surface` returns to `rotation`.

**Given** the Bar is revealed,
**When** a touch lands on the gear icon specifically,
**Then** the Device transitions to Settings (Story 3.1) instead of retracting.

## Epic 3: Settings View with Network Status, Guideline, and Reboot

Add the full-screen Settings view — status snapshot, mode-branched guideline copy, and an immediate-fire Reboot control — as a third `active_view`, reachable only from the Bar's gear icon and always exiting straight back to Rotation.

### Story 3.1: Open Settings view from the gear icon with a captured status snapshot

As Minh,
I want tapping the gear icon to open a full-screen Settings view showing my current network info,
So that I can read the Device's IP or Setup AP details without hunting through menus.

**Acceptance Criteria:**

**Given** the Bar is revealed and the user taps the gear icon,
**When** the tap registers,
**Then** `active_surface` transitions to `settings`, Rotation is suspended entirely (not just paused), and the Bar is hidden.
**And** `App` copies the existing reduced `kind`/`ssid`/`ip` state once into `AppState.settings_status_snapshot`; `settings_view.py` renders only that snapshot, never live state, and it is not updated again until the next Settings entry.

**Given** Settings is open,
**When** it renders,
**Then** it draws full-screen through the existing `compositor.render()` path as a third `active_view` value alongside `VIEW_CLOCK`/`VIEW_CALENDAR`, and the Clock/Calendar view does not draw underneath it.
**And** layout is top-aligned: 28px top padding, then the status line; 18px gap, then the guideline line; a larger gap, then the Reboot button positioned lower with clear separation from the block above.
**And** no back/close icon is present anywhere on the view.

### Story 3.2: Render status and mode-branched guideline copy

As Minh,
I want the Settings view to show my exact connection info and instructions in plain language,
So that I know precisely what to type into a browser to reach the Config page.

**Acceptance Criteria:**

**Given** `settings_status_snapshot.kind` is Setup AP mode,
**When** Settings renders,
**Then** the status line shows SSID + gateway (16px bold, 1px letter-spacing, `digit-primary`), and the guideline line reads exactly "Connect to Wi-Fi `<SSID>` then browse to `<gateway>`" (13px regular, 0.5px letter-spacing, `digit-secondary`).

**Given** `settings_status_snapshot.kind` is station mode,
**When** Settings renders,
**Then** the status line shows the IPv4 address, and the guideline line reads exactly "Browse to http://`<ip>`", same typography roles as above.

### Story 3.3: Reboot control with Press Flash, no confirmation

As Minh,
I want a single tap on REBOOT to restart the Device immediately,
So that I can recover from a stuck state without extra steps.

**Acceptance Criteria:**

**Given** Settings is open,
**When** the Reboot button renders,
**Then** it shows the label "REBOOT" (14px bold, 2px letter-spacing, all-caps, `digit-secondary` at rest — never `unsynced-bg` red), sized with a fingertip-generous tap-target rect larger than its visible text bounds.

**Given** the user taps the Reboot button,
**When** the tap registers,
**Then** a Press Flash (`#ffe9b8`) shows briefly on the button, then `RebootPort.reset()` is called synchronously with no confirmation dialog or second tap required.
**And** no other Bar icon or Settings element triggers a reboot, now or when more icons are added later.

### Story 3.4: Settings idle timeout and outside-tap dismissal

As Minh,
I want Settings to close itself if I walk away, or close immediately if I tap outside Reboot,
So that the Device never sits in Settings indefinitely and always finds its way back to the clock.

**Acceptance Criteria:**

**Given** Settings is open with no further touch activity,
**When** `TOUCH_IDLE_TIMEOUT_MS` (the same shared 15s constant used by the Bar, not a separate value) elapses,
**Then** `active_surface` returns to `rotation`, resuming the view that was showing before Rotation was interrupted, with its dwell deadline freshly re-armed from `now`.

**Given** Settings is open,
**When** a touch lands outside the Reboot button's tap target,
**Then** Settings closes immediately (same treatment as the Bar's outside-tap dismissal) and `active_surface` returns to `rotation`.
**And** there is no path from Settings back to Bar-Revealed — closing Settings always returns straight to Rotation.
