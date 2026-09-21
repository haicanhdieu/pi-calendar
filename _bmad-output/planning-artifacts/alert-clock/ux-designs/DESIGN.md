---
name: Alert Clock Buzzer
description: Buzzer interaction visual design for Pico W calendar clock.
status: in-progress
colors:
  bg: '#0a0a0a'
  digit-primary: '#3dff7a'
  digit-secondary: '#ffb238'
  unsynced-bg: '#ff4d4d'
  unsynced-text: '#0a0a0a'
  web-bg: '#12161c'
  web-surface: '#1b212a'
  web-border: '#2a323d'
  web-text-primary: '#e8ecf1'
  web-text-secondary: '#9aa5b1'
  web-accent: '#7c6cf6'
  web-accent-text: '#0a0f16'
  web-danger: '#ff5c5c'
  web-success: '#3ddc84'
typography:
  alert-time:
    family: '-apple-system, "Helvetica Neue", Arial, sans-serif (device: bold sans bitmap font)'
    size: 88px
    weight: 700
    tabular-nums: true
  alert-label:
    size: 16px
    weight: 700
    letter-spacing: 2px
  action-label:
    size: 14px
    weight: 700
    letter-spacing: 1px
  support:
    size: 14px
    letter-spacing: 2px
  web-page-title:
    fontFamily: '-apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 20px
    fontWeight: 700
  web-body:
    fontFamily: '-apple-system, "Segoe UI", Roboto, sans-serif'
    fontSize: 15px
    fontWeight: 400
rounded:
  badge: 3px
spacing:
  frame-padding: 10px 12px
  web-page-padding: 20px
  web-field-gap: 16px
  web-section-gap: 28px
components:
  active-alert:
    background: '{colors.bg}'
    headline-color: '{colors.digit-primary}'
    time: '{typography.alert-time}'
  stop-target:
    min-size: 120px 70px
    label: '{typography.action-label}'
  postpone-target:
    min-size: 120px 70px
    label: '{typography.action-label}'
  unsynced-badge:
    background: '{colors.unsynced-bg}'
    text: '{colors.unsynced-text}'
    radius: '{rounded.badge}'
  alert-settings-section:
    background: '{colors.web-bg}'
    surface: '{colors.web-surface}'
    border: '{colors.web-border}'
  web-primary-button:
    background: '{colors.web-accent}'
    foreground: '{colors.web-accent-text}'
sources:
  - ../prds/prd.md
  - ../prds/addendum.md
  - ../../pico-w-calendar-clock/ux-designs/DESIGN.md
  - ../../pico-w-calendar-clock/ux-designs/EXPERIENCE.md
  - ../../wifi-config/ux-designs/DESIGN.md
  - ../../wifi-config/ux-designs/EXPERIENCE.md
updated: 2026-09-21
---

## Brand & Style

Alert Clock has two visual contexts. Active alert extends Pi Calendar Clock's
instrument-panel identity for rare, high-attention moments. It is full-screen and text-first: it
must be readable and resolvable from a desk, without icons, cards, chrome,
gradients, or animation. Normal clock/calendar screen returns after resolved
occurrence.

Alert Settings extends Wi-Fi Config's dark, phone-first utility surface. It is
quiet, single-column, close-viewed, and distinct from TFT green/amber language.
This document owns both surfaces; spines win over mocks. Visual references:
[Alert Settings](mockups/key-alert-settings.html) and [Active Alert TFT](mockups/key-active-alert.html).

Green remains hero; amber supplies support. Red remains exclusive to
`UNSYNCED`, including during active alert. Alert state communicates through
plain language, stable hierarchy, sound, and large labeled controls—not a new
color or icon language.

## Colors

Inherits base Pi Calendar Clock palette exactly.

- **Background (`{colors.bg}`)** — full-bleed active-alert canvas.
- **Primary (`{colors.digit-primary}`)** — active-alert headline and current
  alert time; use only for current focal information.
- **Secondary (`{colors.digit-secondary}`)** — supporting state, combined-alert
  count, deferred due-time confirmation, and control labels when hierarchy
  permits.
- **Unsynced (`{colors.unsynced-bg}` / `{colors.unsynced-text}`)** — fixed
  top-right `UNSYNCED` badge only. Never use red for alert, Stop, Postpone,
  failure, or decoration.

No visual color is specified for buzzer/control failure beyond preserved
`UNSYNCED` treatment. [ASSUMPTION: bounded failure state uses text hierarchy
within inherited green/amber palette until hardware/render failure UX is
specified.]

Alert Settings inherits Wi-Fi Config palette: `{colors.web-bg}` canvas,
`{colors.web-surface}` rows/forms, `{colors.web-border}` dividers,
`{colors.web-text-primary}` and `{colors.web-text-secondary}` copy,
`{colors.web-accent}` primary actions/focus, `{colors.web-success}` saved
confirmation, and `{colors.web-danger}` validation/delete only. Never bring
TFT green/amber into browser Settings; never use browser red on TFT.

## Typography

Inherits base bold sans bitmap/vector treatment and fixed-width numerals where
time changes. Active-alert time uses `{typography.alert-time}` only when fit
permits; support text uses `{typography.support}` and labels use
`{typography.action-label}`. Labels remain text, never icons or abbreviated
glyphs.

- **Alert headline** — `ALERT`, explicit and distance-legible.
- **Occurrence time** — local due/re-alert time, tabular numerals.
- **Combined count** — explicit text such as `2 ALERTS`, never count alone.
- **Actions** — exact labels `STOP` and `POSTPONE <N> MIN`; no “Snooze”.
- **Confirmation** — explicit deferred due time; no transient icon-only proof.

Alert Settings uses `{typography.web-page-title}` for `DEVICE SETTINGS` and
`{typography.web-body}` for list/form content. Section labels inherit Wi-Fi
Config's 12px bold uppercase treatment; field labels are 13px/600 and buttons
15px/700 system sans. Browser controls may use sentence case; TFT actions stay uppercase.

## Layout & Spacing

Active alert occupies full 320×240 landscape frame and replaces normal
Rotation, Bar, and Settings content. Three fixed vertical bands: top 25% for
`ALERT`, due/current time, optional joined count and `UNSYNCED`; middle 50% is
one large full-width `STOP` target; bottom 25% is one full-width `POSTPONE <N>
MIN` target. `UNSYNCED` stays fixed top-right and does not reflow alert
hierarchy. [ASSUMPTION: final touch calibration validates target boundaries.]

Postpone confirmation briefly replaces top information band before normal
Rotation returns; it never rebuilds normal screen while buzzer needs resolution.
Reference: [Active Alert TFT mock](mockups/key-active-alert.html).

Alert Settings is one phone-width Config page, no desktop breakpoint. Preserve
20px page padding, 16px field gap, and 28px section gap. Insert one `ALERTS`
section in existing flat settings list: alert rows, `ADD ALERT`, then global
`POSTPONE DELAY`. Row edit controls expand inline; no deep navigation or modal stack.
Reference: [Alert Settings mock](mockups/key-alert-settings.html).

## Elevation & Depth

None. Flat, single-layer instrument panel. Action targets are bounded by
position, label, and text hierarchy, not cards, shadows, modal overlays, or
raised button chrome. Green digit glow may retain inherited lit-display effect.

## Shapes

No new shape language. Inherit minimal `{rounded.badge}` only for `UNSYNCED`.
Active-alert action regions remain unrounded unless target display driver makes
that impossible; no pills, circles, icons, or card containers.

Alert Settings inherits 10px input/button corners, 14px rows/cards, and pill
status badges from Wi-Fi Config. Those rounded browser controls never transfer to TFT.

## Components

- **Active-alert screen** — full-bleed `{colors.bg}`. Displays `ALERT`, local
  occurrence time, optional explicit combined count, both action targets, and
  `UNSYNCED` when time source is unsynced.
- **Stop target** — text-only `STOP`, full-width middle 50% band. No
  destructive red treatment.
- **Postpone target** — text-only `POSTPONE <N> MIN`, full-width bottom 25%
  band; `<N>` is saved global whole-minute delay.
- **Deferred confirmation** — text-only confirmation naming deferred due time,
  shown before return to normal Rotation. [ASSUMPTION: duration unspecified;
  must be long enough to read and must not require acknowledgement.]
- **Combined occurrence count** — appears only when two or more Alerts joined
  one occurrence; uses explicit count wording.
- **Unsynced badge** — inherited fixed top-right component. Preserve it where
  alert layout permits; no alternate alert-colored state.
- **Buzzer/render failure state** — bounded text-only state, no secret or raw
  diagnostic. [ASSUMPTION: exact user-facing wording and recovery affordance
  remain unspecified.]
- **Alert Settings section** — `ALERTS` label; rows show local time, enabled
  state, readable recurrence. Max-ten limit keeps `ADD ALERT` unavailable with explanation.
- **Alert editor** — inline expanded row/form: time, enabled state, weekday
  selection, Save, Delete. No labels, sound, volume, or per-alert Postpone controls.
- **Weekday selector** — seven text labels with selected state; multi-select;
  no selection means one-time.
- **Global Postpone delay** — whole-minute control, default 10, labeled
  `POSTPONE DELAY (MIN)`, range 1–60. [ASSUMPTION: range]
- **Delete confirmation** — browser confirmation uses `{colors.web-danger}` only.
- **Saved status** — brief `{colors.web-success}` text/banner confirmation.

## Do's and Don'ts

- **Do** make Stop and Postpone visible together, vertically separate, and labeled.
- **Do** give Stop middle 50% of active TFT; Postpone gets bottom 25%.
- **Do** use `Postpone`, never `Snooze`, in every device surface.
- **Do** preserve `UNSYNCED` badge during active alert where layout permits.
- **Do** use audio plus explicit text/action labels; no color-only alert signal.
- **Don't** use red for active-alert urgency, Stop, failure, or primary actions.
- **Don't** add alarm labels, custom sound choices, volume, melodies,
  vibration, remote controls, or per-alert postpone controls.
- **Don't** make Alert Settings resemble TFT active alert, or put browser
  Settings controls on TFT.
