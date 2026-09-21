# Reconcile — Core Clock UX

## Extracted UX decisions

- Alert inherits 320×240 landscape ILI9341 form factor, single-owner desk-object posture, and DESIGN.md as visual identity authority.
- Base visual language: `#0a0a0a` near-black field; green hero (`{colors.digit-primary}`); amber supporting tier (`{colors.digit-secondary}`); bold sans, fixed/tabular numerals; flat panel, no cards, shadows, overlays, gradients, icons, or decorative motion.
- Red (`{colors.unsynced-bg}`) remains exclusive to text-bearing `UNSYNCED` state. Alert must not repurpose it as generic urgency color.
- Base normal surfaces are Clock and Calendar, automatic plain-cut rotation; active alert temporarily replaces them rather than expanding normal IA.
- Time trust stays visible through text `UNSYNCED`, not color alone. Base clock/date format and month-grid behavior resume after alert resolution under alert PRD's last-normal-view assumption.
- Physical legibility remains floor: high contrast, at-distance reading, no shrinking existing core text to add alert density.

## Conflicts / gaps

- Core EXPERIENCE says no touch, buttons, navigation, settings screen, or input affordances; alert PRD overrides these claims narrowly during active alert. Alert UX must state this scoped override so normal Clock/Calendar remain non-interactive.
- Core DESIGN reserves red exclusively for unsynced badge, but alert requires high-attention full-screen state. No approved alert accent, control color, or active-screen visual hierarchy exists.
- Core typography tokens cover time/calendar/badge only. Alert title, active time, control labels, countdown/combined count, confirmation, and failure-state tokens are absent.
- Core flat/no-overlay rule conflicts with alert preemption only if alert is modeled as overlay; treat active alert as its own full-screen surface, not modal card.
- `UNSYNCED` badge placement is fixed top-right and never reflows content, but PRD says preserve it only where alert layout permits. Need explicit alert-screen precedence/placement decision.
- Core mockups cover Clock and Calendar only. Alert screen requires new reference if layout choices affect behavior.

## Omitted by source boundary

- Core UX has no alert settings or alarm-management behavior; do not infer browser IA, alert fields, recurrence controls, or web auth from it.
- Core 30 s Clock / 5–10 s Calendar dwell values remain normal-rotation behavior, not alert timing.
- Core Wi-Fi recovery journey informs unsynced meaning only; it does not define alert offline, power-loss, hardware-failure, or touch feedback behavior.
