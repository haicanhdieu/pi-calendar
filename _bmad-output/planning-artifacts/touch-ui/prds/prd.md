---
title: Touch-Screen UI/UX Redesign
status: draft
created: 2026-09-13
updated: 2026-09-13
---

# PRD: Touch-Screen UI/UX Redesign

## 0. Document Purpose

This PRD scopes the touch-screen menu/settings redesign for the Pi Calendar Clock device, now that its TFT panel has a wired touch overlay (`main.py` initializes `TOUCH_CS`; XPT2046-compatible controller per `src/config.py`). It is a companion to [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) (core clock/calendar vision, Device, Time source, Clock view, Calendar view) and [wifi-config prd.md](../../wifi-config/prds/prd.md) (Setup AP, Config page, the browser-based settings this PRD's Settings view points users toward). It does not repeat either — it defines what happens when the user touches the screen. FR/UJ IDs are local to this document and restart from FR-1/UJ-1; name this PRD alongside the ID when referencing it elsewhere.

This PRD supersedes the base PRD's §5 non-goal "not building a settings UI or physical input handling in v1" and its UJ-1 assumption of no settings/input flow — that held only until touch hardware existed.

Source: a `bmad-party-mode` design session (2026-09-13) with Mary, John, Sally, Winston, and Amelia; decisions below were locked there.

## 1. Vision

The Device's screen currently shows a network status line (Setup AP's SSID+gateway, or the station IP once connected) permanently, in a corner, whether anyone's looking or not — a debugging leftover, not a feature. With touch now available, the Device gets an on-demand Settings view instead: invisible until asked for, reachable in two taps, and built to grow. Touching the screen surfaces a bottom bar; tapping its gear icon opens Settings, which shows the network status (now purposeful — read it, then go configure via the browser) and a Reboot control. Everything else about the Device — the Clock view / Calendar view auto-rotation — is untouched.

## 2. Target User

Same single owner as [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) §2 (Minh, single-owner desk device, not multi-user).

### 2.1 Key User Journeys

- **UJ-1 (ambient glance, unchanged).** Minh walks past the Device. It's mid-rotation between Clock view and Calendar view, no network status visible, nothing to look at but the time and date. He doesn't touch it. Nothing changes from today's behavior.
- **UJ-2 (checking the IP to reach the Config page).** Minh wants to change a setting on the Device (per [wifi-config prd.md](../../wifi-config/prds/prd.md) UJ-3) but doesn't remember its address. He taps the screen; the bottom bar slides up with a single gear icon; rotation pauses. He taps the gear; the Settings view opens showing the station IP and a line reading "Browse to http://<ip>". He reads it, taps nothing else, and the Settings view times out back to the Clock/Calendar rotation while he opens a browser on his phone.
- **UJ-3 (reboot after a stuck state).** The Device is behaving oddly. Minh taps the screen, taps the gear, and taps Reboot inside Settings. The Device restarts. **Edge case:** if Minh walks away from an open Settings view without touching Reboot, it times out and resumes rotation on its own — it never sits open indefinitely.

## 3. Glossary

*(Extends [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) §3 and [wifi-config prd.md](../../wifi-config/prds/prd.md) §3 — Device, Clock view, Calendar view, Setup AP, Config page.)*

- **Rotation** — the existing timed auto-switch between Clock view and Calendar view.
- **Bar** — the bottom-docked touch menu that slides up over the current view on touch, holding icon buttons. Retracted (hidden) or Revealed (visible) state.
- **Settings icon** — the one Bar icon in v1 (gear); opens the Settings view. Bar is built as an icon list so more icons can be added later without redesign.
- **Settings view** — the full-screen view opened by the Settings icon, showing the Network status line, the Guideline line, and the Reboot control.
- **Network status line** — the Setup AP's SSID+gateway, or the station IP once connected — the same data the Device already tracks, now shown only in the Settings view instead of as a permanent overlay.
- **Guideline line** — one line of instructional text in the Settings view telling the user how to reach the Config page, worded per whether the Device is in Setup AP or station mode.
- **Idle timeout** — the fixed delay (5-8s) after which an inactive Bar or Settings view automatically closes and Rotation resumes.

## 4. Features

### 4.1 Ambient Status Cleanup

**Description:** Removes the always-on network status overlay from the Clock view and Calendar view; that information moves into the Settings view (§4.3). Rotation itself is unaffected.

#### FR-1: Hide network status overlay by default

Device does not render the Network status line on the Clock view or Calendar view during Rotation.

**Consequences (testable):**
- Neither Setup AP (SSID+gateway) nor station IP text appears anywhere during normal Rotation.
- The existing UNSYNCED badge (unrelated overlay) is unaffected and continues to render as today.

**Out of Scope:**
- Any other on-screen indicator change (badge, fonts, layout of Clock/Calendar views themselves).

### 4.2 Touch-Reveal Bar

**Description:** A touch anywhere on the screen during Rotation reveals the Bar; it holds the Settings icon (only one for v1) and auto-retracts when unused. Realizes UJ-2, UJ-3.

#### FR-2: Reveal Bar on touch

While Device is in Rotation, any touch on the screen transitions it to Bar-Revealed: Rotation pauses, and the Bar slides up from the bottom edge over roughly 200-300ms. [ASSUMPTION: Rotation resumes on whichever view was showing when the Bar closed, rather than restarting its own timer from the beginning — confirm.]

**Consequences (testable):**
- A touch during Rotation always produces a visible Bar within one animation cycle; it never silently ignores the touch.
- Bar renders as an icon list container, not a single hardcoded button — adding a second icon later requires no state-machine change.
- While Bar-Revealed, Rotation's own view-switch timer does not fire.

#### FR-3: Auto-retract and outside-tap dismiss

Bar-Revealed returns to Rotation after the Idle timeout (5-8s) with no further touch, or immediately on a touch outside the Bar's own area.

**Consequences (testable):**
- No touch activity for the full Idle timeout while Bar-Revealed closes the Bar and resumes Rotation.
- A touch landing outside the Bar (but not on the Settings icon) closes the Bar immediately without opening Settings.
- A touch landing on the Settings icon opens the Settings view (FR-4) instead of retracting.

**Feature-specific NFRs:**
- Bar reveal/retract animation must not visibly stutter or blank the screen mid-transition. [ASSUMPTION: acceptable on current hardware — no profiling done yet; flag if the ILI9341 driver's fill rate can't hold ~200ms slide at readable frame pacing.]

**Notes:**
- [NOTE FOR PM] Touch debounce / palm-rejection on the touch panel is unresolved — see §8 Open Questions. A false-triggering panel would make FR-2 read as broken even though the state machine is correct.

### 4.3 Settings View

**Description:** Reached only via the Settings icon; shows the Network status line, a Guideline line pointing at the browser-based Config page, and a Reboot control. Times out back to Rotation like the Bar. Realizes UJ-2, UJ-3.

#### FR-4: Open Settings view

Tapping the Settings icon while Bar-Revealed transitions the Device to Settings, suspending Rotation entirely (not just pausing the timer — Bar is also hidden while Settings is open).

**Consequences (testable):**
- Settings view renders full-screen; Clock view / Calendar view do not draw underneath it.
- Network status line shown matches the Device's current connection state: Setup AP mode shows SSID + gateway; station mode shows the IPv4 address — reusing the existing `kind`-branched status dict (`src/ui/components.py`), just rendered full-size instead of as a corner strip.
- Guideline line is worded per the same branch: Setup AP mode reads "Connect to Wi-Fi `<SSID>` then browse to `<gateway>`"; station mode reads "Browse to http://`<ip>`".

#### FR-5: Reboot control

Settings view includes a Reboot button, deliberately absent from the Bar itself.

**Consequences (testable):**
- Tapping Reboot restarts the Device (soft reset). [ASSUMPTION: no confirmation dialog for v1 — a single tap reboots immediately, since Settings is already two taps deep from Rotation. Confirm if a confirm-step is wanted given reboot has real consequences (drops any in-progress Wi-Fi client).]
- No other Bar icon triggers a reboot, now or when more icons are added later.

#### FR-6: Settings idle timeout

Settings view returns to Rotation after the Idle timeout (5-8s) with no touch activity, same as the Bar (FR-3).

**Consequences (testable):**
- Settings view never remains open indefinitely once the Device is untouched.
- Timeout duration is shared with the Bar's (single configured value), not a separate one, so the Device's touch behavior feels consistent across both surfaces. [ASSUMPTION: one shared constant rather than two independently tunable timeouts — confirm if Settings should stay open longer than the Bar.]

**Out of Scope:**
- Any Settings content beyond Network status line, Guideline line, and Reboot (brightness, Wi-Fi reset, alarm, etc.) — see §5, §6.2.

## 5. Non-Goals (Explicit)

- Not adding any Bar icon beyond Settings in v1 — the icon-list architecture exists so future features (brightness, alarm, etc.) can be added later, but none are being built now.
- Not exposing Wi-Fi credential entry, color scheme, or any other Config-page setting on-device — those stay in the browser Config page per [wifi-config prd.md](../../wifi-config/prds/prd.md); the Device's Settings view only shows how to get there plus Reboot.
- Not placing the Bar on the left or right edge — bottom only, per the party-mode design decision (landscape 320x240 has more vertical slack than horizontal; Device is wall/desk-mounted, tapped top-down rather than held).
- Not solving touch debounce / palm-rejection hardening in this PRD — flagged as an open risk needing an owner, not designed here (see §8).
- Not changing Rotation's own cadence or the Clock view / Calendar view content — out of scope per the design session, unchanged from the base PRD.

## 6. MVP Scope

### 6.1 In Scope
- Removing the always-on Network status overlay from Rotation.
- Touch-anywhere Bar reveal (bottom-docked), single Settings icon, icon-list architecture for future growth.
- Bar and Settings auto-retract on Idle timeout (5-8s) or outside tap.
- Settings view: Network status line + Guideline line (Setup AP vs. station branch) + Reboot control.

### 6.2 Out of Scope for MVP
- Additional Bar icons (brightness, alarm, etc.) — deferred until a concrete feature needs one. [NOTE FOR PM: bar architecture should make this cheap when it happens — verify at implementation time.]
- Touch debounce / palm-rejection tuning — deferred pending an owner (§8).
- Reboot confirmation step — deferred unless testing shows accidental reboots are a real problem.
- Any new content on the Settings view beyond network status + guideline + reboot.

## 7. Success Metrics

Hobby-scale: no formal instrumentation planned.

**Primary**
- **SM-1**: Minh can reach the Device's IP/Config-page instructions in two taps from an idle screen, without reading documentation. Validates FR-2, FR-4.

**Counter-metrics (do not optimize)**
- **SM-C1**: Bar/Settings reveal should not become the default resting state of the screen — if Minh finds himself leaving Settings open "for convenience," the timeout is miscalibrated and defeats the point of hiding status by default. Counterbalances SM-1.

## 8. Open Questions

1. Touch debounce / palm-rejection: does the current touch controller/driver need software debounce to avoid false Bar reveals from vibration, dust, or incidental contact? No owner assigned yet — flagged by Grumbal (adversarial reviewer) in the design session as a real risk to ship quality, not a nit.
2. Does Rotation resume from where it left off, or restart its cycle, after Bar/Settings closes? (FR-2 assumption.)
3. Is a single shared Idle timeout constant for both Bar and Settings acceptable, or should Settings linger longer since reading network info takes more attention than glancing at a menu? (FR-6 assumption.)
4. Should Reboot require a confirmation tap given it drops any in-progress network activity? (FR-5 assumption.)

## 9. Assumptions Index

- §4.2 FR-2 — Rotation resumes from its last-shown view rather than restarting its cycle after the Bar closes.
- §4.2 (Feature-specific NFRs) — current ILI9341 driver can hold a ~200ms slide animation without visible stutter; unverified.
- §4.3 FR-5 — Reboot fires immediately on tap, no confirmation dialog, in v1.
- §4.3 FR-6 — Bar and Settings share one Idle timeout constant rather than two independently tunable values.
