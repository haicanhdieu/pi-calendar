---
id: SPEC-clock-upcoming-events
companions: []
sources: ["https://claude.ai/code/artifact/263328da-aad8-4b48-9c06-c92ed3e8671e"]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Clock Screen Upcoming Events

## Why

A vision to realize: the Clock screen redesign (today top-left, luna-today top-right, clock recentered — already shipped) reserved a 56px band at the bottom of the screen specifically so this feature could land without another layout change. Right now that band is empty pixels. Filling it lets someone glance at the always-on clock face and see what's coming next without switching screens — the whole point of the corner-row redesign was to make room for this.

## Capabilities

- **CAP-1**
  - **intent:** User glances at the Clock screen and sees their next up-to-3 upcoming events without leaving the clock view.
  - **success:** With 3+ upcoming events queued, the Clock screen renders exactly 3 rows, each as time + title. With 1 or 2 events, exactly that many rows render and no placeholder fills the rest. With 0 events, the band renders nothing — no heading, no empty-state text.

## Constraints

- Each event row is one line: `HH:MM  Title`, `FONT_SETTINGS_STATUS` scale (16px), `COLOR_SECONDARY`, left-aligned at `CLOCK_CORNER_PAD_X_PX`. No per-row fill/badge box — that styling is reserved for the unsynced-clock alert.
- Rows must fit the existing reserved geometry: `config.CLOCK_EVENTS_BAND_H_PX = 56` at y=184..240 on the 320×240 ILI9341 screen. No change to the clock or corner-row layout math in `_layout()`.
- Long titles are measured (`display.measure_text`) and truncated with an ellipsis to fit the row width — never overflow past x=310 or wrap to a second line.
- Must follow `ClockView`'s existing dirty-region redraw discipline (cache dict, full-vs-partial redraw) — the events band participates in `_full_redraw`'s cache-and-compare, not a separate uncoordinated draw path.

## Non-goals

- Sourcing or syncing event data (ICS import, calendar API, manual entry UI) — see Open Questions.
- Tapping/selecting an event row, an event-details view, and multi-day/all-day event handling.

## Success signal

- On the physical device (or the DisplayPort test double), queuing 0, 1, 2, and 3+ upcoming events each produce the exact row count specified in CAP-1's success criterion, with no layout regression to the clock or corner rows above.

## Assumptions

- Events arrive at `ClockView` already sorted soonest-first and pre-filtered to "upcoming" (not past) — this spec's renderer takes a list of up to 3 already-selected events, not a raw event store.

## Open Questions

- What supplies the event data? No `Event` model or event data source exists yet in `src/calendar/` (only `CalendarAnnotation`/`DayCell`/`MonthGrid` for the month-grid view, plus Gregorian/lunar date math — no event list, no ICS/API sync). This spec assumes an events-provider interface will be supplied or stubbed; the concrete source is unresolved and blocks a real (non-simulated) demonstration of CAP-1's success signal.
