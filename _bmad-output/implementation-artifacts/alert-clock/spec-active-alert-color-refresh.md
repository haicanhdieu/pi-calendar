---
title: 'Refresh active alert screen colors and action contrast'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/DESIGN.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Active alert screen colors do not match requested visual hierarchy, and transparent action labels do not provide button-like affordance.

**Approach:** Keep existing 25/50/25 layout and touch bands. Render `ALERT` yellow, alert time blue, a green STOP band, and an orange POSTPONE band. Use near-black text on both bright button backgrounds for strongest contrast; preserve labels, geometry, unsynced badge, and postponed confirmation behavior.

</frozen-after-approval>

## Implementation Notes

- Use existing palette colors for green STOP, orange POSTPONE, and blue time where they match requested hues.
- Add one dedicated bright-yellow alert color if existing palette has no suitable yellow.
- Render button backgrounds across their existing full-width touch bands; button text uses `COLOR_BACKGROUND` (near-black), which gives high contrast on both green and orange.
- Visible action rectangles use 6 px vertical gaps after the time region and between actions; touch hit regions exclude those gaps.
- Add host tests asserting rendered fill and text colors. Device legibility still requires flashed-device inspection.
- Updated `src/ui/alert_view.py`, `src/alert/runtime.py`, and `src/config.py`; updated alert UX source of truth and added render/touch tests.
- Review follow-up aligned touch hit regions with painted buttons and added semantic `COLOR_ALERT_TIME` alias.

## Review Triage Log

- false — UX palette/button-chrome concerns resolved by documenting this explicit active-alert visual override in `DESIGN.md`.
- patch — STOP taps could land in the new top gap; `stop_hit()` now matches painted STOP bounds.
- patch — POSTPONE taps could land in the inter-button gap; `postpone_hit()` now matches painted POSTPONE bounds.
- rejected low — hard-coded 320×240 assertions match device contract; existing host tests are intentionally device-sized.
- rejected low — label color tests plus full render tests cover requested output; exact glyph coordinates are not contract.
- rejected low — palette constants are implementation truth and are covered by rendered color assertions.
- false — active-alert time now uses semantic `COLOR_ALERT_TIME` alias.
- false — combined count remains in its existing top band and no overlap was observed in current geometry/tests.
- false — spec records requested colors, contrast choice, spacing, and implementation mapping.
