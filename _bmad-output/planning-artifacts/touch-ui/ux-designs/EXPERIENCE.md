---
status: final
updated: 2026-09-13
sources:
  - ../../touch-ui/prds/prd.md
  - ../../pico-w-calendar-clock/ux-designs/EXPERIENCE.md
---

## Foundation

**Form factor:** single embedded touch device — 320×240 landscape ILI9341 TFT with an XPT2046-compatible resistive touch overlay, wall/desk-mounted, tapped top-down (never held). No UI system/framework; this spine specifies exact pixel behavior for a MicroPython-driven display, per {design.md} tokens in `DESIGN.md`.

**Visual identity:** `DESIGN.md` (this workspace) — extends the base Pi Calendar Clock DESIGN.md, amending its "no icon set" rule to allow one gear glyph.

**Single owner, no multi-user concerns.** Same target user as the base Device: Minh.

## Information Architecture

Three surfaces, one always-active background state:

```
Rotation (Clock view ⇄ Calendar view, timed auto-switch)
   │  any touch
   ▼
Bar-Revealed (bottom strip, gear icon)
   │  tap gear                    │  idle {idle-timeout} OR outside tap
   ▼                              ▼
Settings (full-screen)     back to Rotation (resumes last-shown view)
   │  idle {idle-timeout} OR outside-tap (not on Reboot)
   ▼
back to Rotation (resumes last-shown view)
```

- **Rotation** is the default/rest state — unchanged from the base Device, now with no permanent status overlay (FR-1).
- **Bar-Revealed** is reachable only from Rotation, via any touch.
- **Settings** is reachable only from Bar-Revealed, via the gear icon.
- There is no path from Settings back to Bar-Revealed — closing Settings always returns straight to Rotation.
- Every surface has exactly one way deeper (touch anywhere → Bar; tap gear → Settings) and two ways back (idle timeout; outside tap) — no surface is a dead end.

## Voice and Tone

Two lines of copy exist on this device, both instructional and terse, matching the Device's existing "instrument panel" register (no friendliness, no punctuation flourish):

- **Guideline line, Setup AP mode:** "Connect to Wi-Fi `<SSID>` then browse to `<gateway>`"
- **Guideline line, station mode:** "Browse to http://`<ip>`"

"REBOOT" is the only button label on the device — all-caps, one word, no verb-phrase softening ("Restart device," "Are you sure?") since there is no confirmation step.

## Component Patterns

- **Touch Bar** — behaves as an icon list with one entry today. Adding a second icon later means appending to the list, not restructuring the reveal/retract/dismiss state machine described below.
- **Gear icon** — the only tappable element while Bar-Revealed. Tapping it is the sole transition into Settings; there is no long-press or secondary gesture.
- **Settings view** — a static, non-scrolling, three-part read: status, guideline, action. Nothing on it updates live while open (status is captured at the moment Settings opens) — reflecting the network state at time of entry, not a live-refreshing panel. [ASSUMPTION: acceptable that status doesn't live-update if the network state changes while Settings happens to be open — confirm, this is an edge case that will essentially never occur in practice.]
- **Reboot button** — single tap, single action, irreversible once tapped (device restarts). No secondary confirmation state exists in this spine (locked in Discovery).

## State Patterns

| State | Entry | What's visible | Exit |
|---|---|---|---|
| Rotation | default / after any timeout or outside-tap dismissal | Clock view or Calendar view, auto-switching, no status overlay | any touch → Bar-Revealed |
| Bar-Revealed | any touch during Rotation | last-shown Clock/Calendar view (frozen, rotation timer paused) + Bar strip sliding up ([mockup](mockups/bar-revealed.html)) | tap gear → Settings; idle {idle-timeout}s → Rotation; outside-Bar tap → Rotation |
| Settings | tap gear while Bar-Revealed | full-screen status + guideline + Reboot, Bar hidden, Clock/Calendar not drawing underneath ([mockup](mockups/settings-view.html)) | tap Reboot → device restarts (terminal); idle {idle-timeout}s → Rotation; outside-Reboot tap → Rotation |

Shared idle timeout constant: **15 seconds**, used identically by Bar-Revealed and Settings (single configured value, per Discovery decision — overrides the PRD's stated 5–8s range).

Rotation always **resumes from the view it was showing when interrupted** — it never restarts its own cycle from the beginning after a Bar/Settings interruption (resolves PRD Open Question #2).

## Interaction Primitives

- **Reveal:** any touch, anywhere on screen, during Rotation → Bar slides up from the bottom edge, 200–300ms.
- **Retract (Bar):** touch outside the Bar's own area (i.e., not on the gear icon) → Bar retracts immediately, no animation delay beyond the reverse of the reveal slide.
- **Retract (Settings):** touch outside the Reboot button's tap target → Settings closes immediately, same treatment.
- **Tap feedback:** every tappable element (gear icon, Reboot button) shows a brief Press Flash (see `{colors.press-flash}` in DESIGN.md) on touch-down, before the resulting transition — confirms the tap registered on a resistive panel that may not be instantaneous.
- **Idle timeout:** no touch activity for 15s while Bar-Revealed or Settings is open → automatic return to Rotation (resumed view), identical mechanism for both surfaces.
- **No gestures beyond single tap** — no swipe, no long-press, no multi-touch, anywhere in this spine.

## Accessibility Floor

Single-owner hobby device, not a general-audience product — the floor here is "reliable under real touch conditions," not WCAG conformance:

- Gear icon and Reboot button both get generous tap targets sized for a fingertip, not the smaller glyph render size itself — the visible glyph can be smaller than its actual touch-detection area.
- Tap feedback (Press Flash) is mandatory on both interactive elements specifically because resistive touch panels can have inconsistent response latency; a tap with no visible acknowledgment reads as broken hardware, not working-but-slow.
- Touch debounce / palm-rejection is explicitly **not** solved by this spine — flagged in the source PRD (§8) as an open risk with no owner. A false-triggering panel would make Bar-reveal read as broken even when this state machine is implemented correctly. [NOTE FOR PM: carried over from PRD — needs an owner before or during implementation.]

## Key Flows

**Minh checks the Device's IP to reach the Config page (realizes UJ-2).** Minh's on the couch, phone in hand, wanting to change a Wi-Fi setting on the Device across the room. He walks over and taps the screen — mid-tap, the Clock view was showing 9:41. The Bar slides up from the bottom in under 300ms: one gear icon, nothing else. He taps it. The screen replaces itself entirely: a bold green IP address at the top, a plain amber line underneath reading "Browse to http://192.168.1.42", and a quiet "REBOOT" sitting lower down that he ignores. He reads the IP once, doesn't touch anything else, and turns back toward the couch. Fifteen seconds later, from across the room, he glances back — the Device is already showing 9:41 again, Clock view resumed exactly where it left off, no trace that Settings was ever open.

**Minh reboots a stuck Device (realizes UJ-3).** The clock's frozen on the same second for too long. Minh taps the screen, the Bar appears, he taps the gear, Settings opens. He taps "REBOOT" — no "are you sure," no second tap required — and the screen goes dark as the Device restarts. This is the flow's climax: one deliberate tap, immediate consequence, no ceremony, because a hobby device that's already misbehaving doesn't need to be argued with before it's allowed to restart.
