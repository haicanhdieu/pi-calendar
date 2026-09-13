# Review — Reality-Check of Versions and Hardware Assumptions

**Target:** `_bmad-output/planning-artifacts/touch-ui/architecture/ARCHITECTURE-SPINE.md`
**Lens:** Was every committed technical decision (versions, library/controller existence, SPI/timing behavior) actually verified against the web or the repo, or asserted from training-data memory?
**Date:** 2026-09-13

## Verdict

Most claims hold up, but the spine commits to a synchronous single-shot touch read and a bare SPI chip-select handoff (AD-2, AD-3) without ever reality-checking XPT2046 electrical/driver behavior — and that gap is not cosmetic: real XPT2046 usage over a bus shared with an ILI9341 needs both slower SPI clock re-negotiation per transaction and multi-sample debouncing, neither of which AD-2/AD-3 account for.

## What was checked against the web

### 1. MicroPython 1.29.0 for Pico W — CONFIRMED, current

- `micropython.org/download/RPI_PICO_W/` lists **v1.29.0 (2026-08-24)** as the latest stable Pico W build, with only a `v1.30.0-preview` ahead of it. So the Stack table's firmware pin is accurate and current as of the spine's `updated: 2026-09-13` date — this is a genuinely fresh release (three weeks old), not a stale assumption.
- The rp2 port in that cycle bumped `pico-sdk` to 2.3.0 and added DMA-pacing support — nothing in that changelog bears on SPI/touch behavior, so no conflict with the spine's design.
- **Severity: none** — this line item was correctly verified, not just asserted.

### 2. XPT2046-compatible touch controller — exists, correctly marked `[ASSUMPTION]`

- XPT2046 (and the pin-compatible ADS7846) are real, current, still-manufactured resistive-touch controller ICs; MicroPython drivers for them exist and are actively referenced (e.g. `rdagger/micropython-ili9341`). The spine's `[ASSUMPTION]` tag and the Deferred note ("Probe before declaring `TouchPort`'s wire protocol final") is the right level of hedging for a part that hasn't been read off the physical module yet.
- **Severity: none** — correctly hedged, not over-committed.

### 3. AD-2's "bounded synchronous single-shot read" — NOT reality-checked, and real driver code disagrees

- Reference MicroPython XPT2046 driver code (e.g. `rdagger/micropython-ili9341/xpt2046.py`) does **not** do a single SPI transaction per read. It collects a run of samples (that driver defaults to 5, with a "confidence" retry loop), computes variance across them, and rejects the read if the samples disagree (`dev <= 50` gate) — because resistive touch panels are electrically noisy and a single ADC conversion is not trustworthy. Some driver variants add explicit inter-sample `sleep()` settling delays and debounce delays around the IRQ edge.
- AD-2 states `TouchPort.read()` is "a single synchronous transfer" called once per `App.step()`, returning an immediate touch/no-touch (and optionally position) result — with no mention of multi-sample averaging, settling time, or a noise-rejection pass. For the boolean "did a touch occur" case this is probably an acceptable simplification (that's genuinely what v1 needs per AD-2's own text), but the same single-shot read is also used to test the touch position against the gear tap-target rect (AD-2, capability map FR-2/FR-3) — and a single unaveraged X/Y sample is the case real driver code exists specifically to avoid jitter/false-position errors on.
- **Severity: Medium.** Not fatal — the spine's Deferred section separately flags "Touch debounce / palm-rejection" as an open, owner-less risk to revisit on hardware, which covers *some* of this. But it doesn't specifically flag that a raw single-shot XPT2046 SPI read is commonly considered too noisy for position decisions, which is a narrower and more concrete risk than generic "debounce." Recommend either explicitly deferring "single-shot position accuracy" alongside the existing debounce deferral, or widening the tap-target rects enough that this class of noise can't flip a decision — and stating that rationale explicitly rather than leaving it implicit.

### 4. AD-3's CS handoff — does not address SPI clock speed mismatch, a well-documented real gotcha

- Multiple independent sources (XPT2046 datasheet-derived guidance, forum threads on ILI9341+XPT2046 shared-SPI setups) converge on: **XPT2046's stable max SPI clock is ~2 MHz**, far below what ILI9341 displays are commonly driven at.
- `src/config.py:19` sets `SPI_BAUDRATE = 40_000_000` — this is the bus speed the existing `Ili9341DisplayPort` already runs at (confirmed in `docs/hardware_configuration.md`: "The current firmware uses a 40 MHz SPI clock"). AD-3 describes the handoff purely in terms of chip-select ownership ("deselects `tft_cs`, selects `touch_cs`, performs its transfer, deselects `touch_cs`, and reselects `tft_cs`") and says nothing about reconfiguring the SPI object's baudrate/mode between the display's 40 MHz and a touch-safe rate before `TouchPort`'s transfer, nor restoring it afterward.
- This is not a hypothetical: reference driver code that pairs ILI9341+XPT2046 on one bus (checked `rdagger/micropython-ili9341`) actually punts on this too — it does no baudrate switching internally and assumes the caller manages it — which means it's a well-known integration gap in the ecosystem, not a solved-for-you problem. AD-3 needs to either (a) explicitly own a `spi.init(baudrate=...)` step as part of the CS handoff it already claims sole ownership of, or (b) state as a design decision that touch reads will run at the display's 40 MHz (with a rationale/risk note), or (c) defer this explicitly like the tap-target-sizing and animation-pacing items already are.
- **Severity: High.** This is the most concrete, checkable gap: AD-3's own stated purpose is "prevents two adapters independently toggling chip-select... and corrupting an in-flight transfer," but leaves an equally real corruption/misread vector (wrong-speed SPI transaction) fully unaddressed. It sits squarely inside AD-3's remit (`TouchPort` "alone" owns the handoff) and should be handled by the same invariant, not silently left to implementation.

### 5. IRQ pin (`TOUCH_IRQ`) — defined in repo but unused by the spine's design; not a version issue but worth flagging

- `src/config.py:14` already defines `TOUCH_IRQ = 26`, and `docs/hardware_configuration.md` explicitly says: "`T_IRQ` is optional for initial polling-based touch support, but connect it now so firmware can detect a touch without continuously reading the controller." AD-2 commits to pure polling (`read()` called once per `App.step()`) and never references `TOUCH_IRQ` at all — not even to note it's deliberately unused for v1.
- This isn't wrong (the hardware doc explicitly allows polling-only for v1), but the spine should say so explicitly rather than silently ignoring an existing, wired, documented config constant — a future reader/implementer could reasonably wonder whether `TouchPort` was supposed to consume `TOUCH_IRQ` and treat its absence as an oversight rather than a decision.
- **Severity: Low.** Documentation/traceability gap, not a technical risk — recommend a one-line note in AD-2 or the Deferred section: "`TOUCH_IRQ`/GP26 is wired but unused by v1's poll-only design; interrupt-driven wake is out of scope here."

### 6. No conflicts found between spine and `hardware_configuration.md` / `config.py` on pin assignments

- `TOUCH_CS = 22` (GP22) and `TOUCH_IRQ = 26` (GP26) in `src/config.py` match `docs/hardware_configuration.md`'s wiring table exactly. `TFT_CS = 17` (GP17) also matches. AD-3's `tft_cs`/`touch_cs` naming maps cleanly onto these existing constants — no renaming or new pin needed.
- The hardware doc's explicit warning ("Do **not** connect the touch `T_CS` pin to the TFT `CS` pin") is structurally honored by AD-3's design (separate CS lines, mutual exclusion via handoff) — consistent, no gap here.

## Summary Table

| # | Item | Verified how | Severity | Action needed |
| - | - | - | - | - |
| 1 | MicroPython 1.29.0 exists/current for Pico W | Web (micropython.org) | None | — |
| 2 | XPT2046 controller real, correctly `[ASSUMPTION]`-tagged | Web | None | — |
| 3 | AD-2 single-shot read vs. real driver multi-sampling | Web (reference driver source) | Medium | Add explicit deferral/rationale for position-noise risk, distinct from generic debounce |
| 4 | AD-3 CS handoff omits SPI baudrate reconfiguration (40 MHz TFT vs ~2 MHz touch max) | Web (XPT2046 datasheet-derived specs) + repo (`config.py` SPI_BAUDRATE, hardware doc) | High | AD-3 should own baudrate switch, or explicitly decide/defer it |
| 5 | `TOUCH_IRQ` wired/documented but unreferenced by AD-2's poll-only design | Repo (`config.py`, hardware doc) | Low | One-line note that IRQ is deliberately unused in v1 |
| 6 | CS pin assignments (TFT_CS/TOUCH_CS) consistent across spine/config/hardware doc | Repo | None | — |
