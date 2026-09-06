---
title: Pico W Universal Calendar & Clock — Product Brief
status: draft
created: 2026-09-05
updated: 2026-09-05
---

# Pico W Universal Calendar & Clock

## What this is

A small, always-on desk device built on a Raspberry Pi Pico W and a 2.4-inch SPI TFT. It shows the time at a glance, and on demand it shows the current month as a calendar. Over time it becomes a *universal* calendar — one that speaks Gregorian and Vietnamese lunar dates side by side, with Can Chi, solar terms, and holidays.

It is a personal build, not a product for sale. The bar is "good enough to sit on a desk and be trusted," not "certifiable."

## Why build it

Off-the-shelf digital clocks are cheap and adequate. What they cannot do is show a Vietnamese lunar date next to the Gregorian one. That combination — âm lịch and dương lịch on the same face — is the reason this project exists and the only part of it that cannot be bought.

Phases 1–4 (display, clock, Gregorian calendar, view switching) are infrastructure. They earn their place by being the platform the lunar calendar lands on. The brief records this so that scope pressure later falls on the right things: the Gregorian half can be minimal, but it must not be shaped in a way that makes the lunar half a rewrite.

## Who it is for

One primary user: the builder, at a desk or on a shelf, glancing at the device several times a day from one to three metres away. Secondary: household members who read the device without knowing anything about it — which sets the legibility bar and rules out any interaction that needs explaining.

The reading distance and the glance-not-stare usage drive most UI decisions: large type, high contrast, no animation that competes with a glance, and no state the user has to remember.

## Scope of the first usable version

**In:**

- ILI9341-class 240×320 SPI TFT driven over SPI0, controller identity verified on the physical module before the driver is finalised.
- A clock view: large HH:MM, smaller seconds, weekday, Gregorian date.
- A calendar view: current month, correct weekday alignment, leap years handled, today highlighted.
- Wi-Fi NTP time sync at boot with periodic re-sync, fixed to Vietnam time (UTC+7).
- A visible indication when the displayed time is not trustworthy (never synced, or stale).
- One push button to switch views, with automatic return to the clock; a configurable auto-rotate as the fallback path when no button is fitted.
- Continuous operation without needing a reset.

**Out of the first version:**

- Vietnamese lunar calendar, Can Chi, solar terms, holidays. Deferred — but the calendar module is structured so these are added, not retrofitted.
- DS3231 RTC. Deferred; NTP covers the powered case, and the RTC exists to cover the unpowered one.
- Touch input (the panel's touch controller is not wired), microSD, any web or app interface, alarms, weather, multiple timezones.

## Decisions made

These were open in the handoff document and are now settled.

**MicroPython, not the C SDK.** The calendar logic — leap years, first-weekday-of-month, and later the lunar conversion — is pure computation with no hardware dependency. In MicroPython that code is byte-identical on a laptop under CPython and on the device, so the highest-risk part of the project gets a real automated test suite for free. Display drivers for this panel class already exist, `ntptime` is in the standard library, and the edit-reboot loop is short. The cost is slower SPI throughput and higher RAM use, both acceptable for a clock that redraws small regions a few times a second. Revisit only if the solar-term math proves too slow or too large in Phase 5.

**Wi-Fi NTP belongs in the first version, not Phase 6.** The handoff document's acceptance criteria require a correct date and weekday, while its phasing gives the first four phases no time source at all — on a cold boot the device would display 2021-01-01. This is an internal contradiction, not a sequencing preference. NTP resolves it with no additional hardware on a board that already has Wi-Fi. DS3231 remains a genuine later addition, and its job is retention across power loss, not initial accuracy.

**One push button in the first version.** The proposed 10-second/10-second auto-rotation means that on roughly half of all glances, a user checking the time is shown a calendar and must wait. That fails the device's primary job. A single button to ground on a spare GPIO with the internal pull-up costs one component and makes the clock the home view with the calendar as a deliberate visit. If the button is ever dropped, the auto-rotate stays available but must be clock-dominant (roughly 50 seconds clock to 8 seconds calendar) rather than balanced.

## Open questions

**Which controller is actually on the panel.** The existing `main.py` contains a class named `ILI9341` with a plausible initialisation sequence, but the identity was assumed, not measured. ILI9341, ST7789, and ILI9488 need different initialisation and differ in pixel format. Reading the controller ID register over SPI is a short, self-contained task and should be the first thing done, before any further display work — a wrong guess presents as a black screen and sends debugging toward wiring that was never at fault.

**Portrait or landscape.** The handoff document specifies portrait 240×320 and draws every layout mockup that way. The existing `main.py` sets 320×240 and hardcodes a landscape MADCTL value. One of the two is wrong, and the seven-column calendar grid is materially easier to lay out in landscape. This needs a deliberate decision, after which the mockups or the code must be brought into line.

**Wi-Fi credential handling.** Where the SSID and password live, and what the device does on a failed connection, are undecided. The failure path matters more than the happy path: displaying a confidently wrong time is worse than displaying an obviously unknown one.

**Where the lunar conversion comes from.** Ported algorithm, precomputed table, or a hybrid. This is the decision that most constrains the calendar module's shape, so it should be made early even though the feature ships late. Precomputed data is cheaper in compute and predictable in memory; a live algorithm is smaller on disk but heavier per call.

## What "done" means for the first version

The device is finished as a first version when it powers on unattended, obtains the correct Vietnam local time over Wi-Fi without intervention, and shows a clock that is readable across a room. The date and weekday are correct, the calendar shows the right month with the correct weekday alignment and today marked, and moving between the two views does not require reading a manual. When the time cannot be trusted, the display says so rather than lying. It runs for days without a reset and without the display degrading.

## Risks worth naming

The controller mismatch is the highest-probability risk and the cheapest to eliminate; it is retired by a twenty-line probe.

Memory fragmentation is the highest-consequence risk. A 240×320 16-bit full framebuffer is roughly 150KB against 264KB of RAM, so full-frame buffering is not available and drawing must work in bands or dirty regions. Long-running MicroPython that allocates per redraw fragments the heap and eventually fails to allocate — which reads as a device that "just stops" after hours, exactly the failure the continuous-operation criterion is meant to exclude. Steady-state drawing should allocate as little as possible, and long-uptime behaviour should be observed rather than assumed.

Solar-term calculation in Phase 5 involves astronomical longitude on a chip with no floating-point unit. It is tractable if computed once per day and cached, and expensive if treated as a per-render call. The mitigation is architectural and should be settled when the calendar module is designed, not when Phase 5 starts.

Wi-Fi is a new dependency in the critical path of a device whose whole job is being correct. Every code path where NTP does not succeed needs to be exercised deliberately.

## Where this goes next

The natural next artifact is a PRD covering the first version, with the two blocking open questions — controller identity and screen orientation — resolved first, since both change the acceptance criteria. The calendar module's interface is worth an architecture pass before implementation, because it is the one design decision that determines whether the lunar calendar is an addition or a rewrite.
