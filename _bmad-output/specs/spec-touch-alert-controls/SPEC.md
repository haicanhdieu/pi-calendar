---
id: SPEC-touch-alert-controls
companions:
  - ../../planning-artifacts/touch-ui/ux-designs/DESIGN.md
  - ../../planning-artifacts/touch-ui/ux-designs/EXPERIENCE.md
  - ../../planning-artifacts/alert-clock/prds/prd.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Touchscreen Alert Controls

## Why

A pain to solve: users must open the web settings page to enable or disable alerts, making a common clock task inconvenient. Give users direct access from the touchscreen.

## Capabilities

- **CAP-1**
  - **intent:** User opens an alert screen from a new clock icon in a separate bottom-bar button immediately right of the Settings button, then enables or disables any stored alert with its visible control.
  - **success:** The alert screen lists every stored alert with its time, recurrence, and current enabled state. Tapping its Enable or Disable control changes that alert's persisted state, and the scheduler follows the new state.

## Constraints

- Add clock icon to existing bottom touch bar, immediately right of Settings button; preserve existing settings entry and touch feedback conventions.
- Preserve existing 320×240 display and 36 px bottom-bar height. Divide bar into two equal, separate icon-only buttons: Settings gear on left, Alerts clock on right. No button labels.
- Keep each button's 48×48 px touch target centered in its half of the bar; target extends 6 px above and below the 36 px visible bar.
- Give each icon the existing amber resting color and brief press-flash feedback on touch-down.
- Alert controls change the existing persisted enabled state. They do not delete alerts; disabled alerts remain visible.
- Each alert's enable/disable control shows its current state by color: enabled uses existing green primary (`#3dff7a`); disabled uses existing amber secondary (`#ffb238`). Keep text/icon contrast readable against each control. Red remains reserved for the unsynced warning.
- Show five alert rows per page, with 80×30 px state controls and 8 px vertical gaps; use PREV/NEXT for up to ten stored alerts.
- Keep Alerts open for 60 seconds of inactivity; successful toggles and page navigation renew this timeout. Outside taps dismiss to normal rotation.

## Non-goals

- Creating, editing, or deleting alerts on the touchscreen.
- Changing alert recurrence, scheduling, sound, or active-alert behavior.
- Removing existing web alert administration.

## Success signal

On the device, user can open the alert screen from the bottom bar, identify each stored alert and its enabled state, toggle one alert, and see that state persist and affect whether its next occurrence can trigger.

## Assumptions

- Alert rows reuse existing time and recurrence details.
- Outside tap closes Alerts; 60 seconds of inactivity closes it. Successful toggle and page taps renew the timeout.

## Touch Bar Mockup

Alert screen design: [Touch UI DESIGN.md](../../planning-artifacts/touch-ui/ux-designs/DESIGN.md#alert-list-view) and [screen mockup](../../planning-artifacts/touch-ui/ux-designs/mockups/alert-screen.html).

320×240 display; bar is 36 px tall. Button targets are 48 px tall, centered on the bar, and extend 6 px beyond its visible top and bottom edges. Vertical proportions shown approximately; glyphs only, no labels.

```text
┌────────────────────────────────┐
│                                │
│             CLOCK              │
│                                │
│                                │
│                                │
│                                │
├────────────────┬───────────────┤ ← bar top (204 px)
│       ⚙        │       ◷       │
└────────────────┴───────────────┘ ← screen bottom (240 px)
       Settings         Alerts
         48×48           48×48       ← touch targets; extend 6 px above bar
```
