---
id: SPEC-wifi-config
companions: [override-trace.md]
sources: [.temp/feeder-vs-pi-calendar-wifi-setup.md, .temp/page-redesign-proposal.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Setup-AP and admin-page HTML/CSS/JS redesign

## Why

**A pain to solve.** The Pico W (RP2040, MicroPython, ~160-190KB usable heap with a non-compacting mark-sweep GC) intermittently crashes with `MemoryError` when serving its own web pages. Diagnosed and hardware-reproduced this session: `src/device/web/page_setup_content.py`'s ~4.3KB embedded JS (a client-side fetch/scan/DOM-render SPA-style flow) and ~1.8KB embedded CSS are too large to reliably allocate on a fragmented device heap. A comparison against a working sibling project (feeder — no embedded CSS/JS at all) and community research both point the same direction: shrink the on-device page payload. This spec makes that redesign concrete and traceable against the wifi-config PRD/UX docs it amends.

## Capabilities

- **CAP-1**
  - **intent:** The setup-AP page (`page_setup_content.py`) renders as a plain server-rendered multi-step HTML form — no client-side fetch, no in-place DOM rendering. `GET /` runs the Wi-Fi scan server-side and renders results as a native `<select>`; "Rescan" is a plain link causing a full-page reload back to `GET /`; submit is a plain `<form method="POST" action="/connect">` full-page reload using the already-implemented `response_join_success`/`response_join_failure` renderers.
  - **success:** `page_setup_content.py`'s JS drops from ~4.3KB to under 1KB (0KB if the optional password show/hide toggle is also dropped); CSS drops from ~1.8KB to under ~0.4KB. The full setup flow (scan → select → password → admin password → connecting → success/failure) works with zero client-side fetch/DOM-render code. A hardware soak test — cold boot, then walk the full setup flow via curl/browser — shows no `web_construct_memory`/`web_asset` MemoryError across at least 10 consecutive cold boots.

- **CAP-2**
  - **intent:** The login/settings pages (`page_login_content.py`, `page_settings_content.py`) stop duplicating shared CSS/JS as inline Python string constants and instead source their styling from one minimal, CDN-hosted classless CSS framework, since these pages only ever serve in `MODE_STATION_ONLINE` where the browser has real internet access.
  - **success:** The two modules no longer contain duplicate copies of `_CONFIG_CSS`. Combined on-device Python source for these two modules' style/script footprint shrinks measurably below the current combined `_CONFIG_CSS` + `_LOGIN_JS` + `_SETTINGS_JS` literal size. Pages remain visually usable (form fields, buttons, accordion settings row) under the new minimal styling.

## Constraints

- The setup-AP page must stay fully self-contained — no CDN or external asset reference. Confirmed against `src/device/network/coordinator.py`: `MODE_SETUP_AP` runs the device's own isolated AP (`network.AP_IF`) with no upstream WAN route for the connecting client, so any external reference simply fails to load there.
- Login/settings pages only serve under `MODE_STATION_ONLINE`, confirmed reachable only after `STA_IF` joins the home Wi-Fi (`coordinator.py` lines 369, 956) — the browser here has real internet access, making CDN viable for CAP-2 specifically and only there.
- The CDN choice for CAP-2 must be a classless/CSS-only framework (e.g. Pico.css/Water.css class) — not jQuery or any JS-heavy library. No page in scope does DOM manipulation heavy enough to justify a JS library payload; keep JS footprint on login/settings pages at or near zero.

## Non-goals

- Wi-Fi join/KDF/session/coordinator logic (`coordinator.py` join flow, PBKDF2 KDF, session table) is unchanged.
- `validation.py`/`verifier.py` are unchanged.
- No offline-caching or service-worker behavior for the CDN asset.
- No visual/branding redesign beyond what the minimal/classless treatment requires.
- The logging-dedup bug in `coordinator._web_failure` (failures logged once, then silently repeat forever) is a known, separate issue — not part of this page-rendering spec.
- No new device-served static-asset route: the CDN choice for CAP-2 needs no local asset, so `GET /static/<name>` in `router.py` is out of scope for this spec.

## Success signal

Ten consecutive cold boots of the flashed device each complete the full setup-AP flow (scan → connect → admin password) and the full login → settings flow with zero `MemoryError`/`web_asset`/`web_construct_memory` serial log lines, while the rendered pages remain visually coherent and usable on a phone browser.

## Assumptions

- Exact CDN provider/URL and CSS framework for CAP-2 (Pico.css vs Water.css vs another classless framework) is left to the implementer, constrained to: classless, CSS-only, small — not materially larger than the `_CONFIG_CSS` it replaces, given it is fetched once and cached by the browser.
- The password show/hide toggle JS on the setup-AP page (~15 lines) may be kept or dropped at implementer discretion; it is not load-bearing for CAP-1's success signal.

## Open Questions

- None outstanding — CDN vs. self-hosted-cached-asset for CAP-2 was resolved in favor of CDN by direct user confirmation; the earlier-considered new static-asset route (once labeled CAP-3) was retracted as unnecessary once the pure-CDN direction was confirmed.
