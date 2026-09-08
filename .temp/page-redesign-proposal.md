# Device page redesign proposal — shrinking on-device CSS/JS footprint

Author: Sally (UX). Investigation only — no source files changed.

## Constraint check (confirmed against code, not assumed)

`src/device/network/coordinator.py`:
- `MODE_SETUP_AP` (line 403, 1001): device runs its own isolated AP on `network.AP_IF` (line 1076). The setup page is served here. **The phone/laptop connected to this AP has no upstream WAN route** — the Pico is not bridging/NAT'ing to anything. A CDN `<link>`/`<script src>` will simply fail to load (timeout, then browser renders unstyled/broken page).
- `MODE_STATION_ONLINE` (line 369, 956) is only entered *after* `STA_IF` successfully joins the home Wi-Fi. Login/settings pages are only served in this mode (per `router.py`'s `route_config_request`). A browser reaching these pages is on the real home LAN, with the home router's normal internet route. **A CDN reference is viable here.**

So: **CDN is a real option for `page_login_content.py` and `page_settings_content.py`, and is a non-starter for `page_setup_content.py`.** Any redesign must keep these two cases visibly separate — don't apply one CSS/JS strategy uniformly across all three modules.

## Recommendation A — Setup-AP page (`page_setup_content.py`): shrink in place, no CDN

This is the largest offender (~1.8KB CSS + ~4.3KB JS) and must stay fully self-contained. Two independent levers, both worth doing:

1. **Cut the JS surface, not just its byte count.** The current JS is a hand-rolled two-screen SPA controller: live SSID list rendering, prefill-on-failure restore, inline show/hide password toggles, fetch-based `/scan` polling, fetch-based `/connect` submit with client-side success/failure branching. feeder's equivalent flow (per the comparison report) is plain multi-page navigation — each state change is a full page reload driven by the server, no client-side state machine at all.
   - Concretely: replace the fetch-based `/connect` submit + client-rendered success/failure banner with a plain `<form method="POST" action="/connect">` and let the *server* render the next screen (this already exists server-side: `response_join_failure`/`response_join_success` in `pages.py` already do exactly this rendering). The JS only needs to exist for: SSID list population from `/scan` (could instead be a plain server-rendered `<select>` populated on each GET reload, no JS `fetch` needed) and password show/hide toggles (a handful of lines, or droppable entirely — show/hide is a nice-to-have, not required for the setup flow to function).
   - Estimated cut: dropping the fetch/scan/banner JS machinery and the two-screen client transition logic removes roughly 70-80% of `_JS` (rough eyeball from the code: the `scan()`/`renderSsids()`/`applyPrefillSelection()`/banner functions are the bulk of the file; only the two toggle-button listeners are simple to keep or drop). Target: **_JS from ~4.3KB down to under 1KB**, or 0 if show/hide toggles are dropped.
   - Tradeoff: loses the "live" no-reload feel (rescan without a page reload, inline validation before submit). Given this is a one-time setup flow run once per device lifetime (or on Wi-Fi change), a full-reload multi-step form is an acceptable UX regression for a large, concrete reliability win. This is a product call — flagging it, not deciding it.

2. **Cut the CSS by dropping design-system polish that isn't load-bearing for a one-time setup form.** ~1.8KB for one form is mostly: custom toggle buttons, banner variants (connecting/failure/success — three separate styled states), rounded-corner card styling, custom radio-like `.ssid-row` buttons. A plain unstyled-but-usable HTML form (native `<select>`, native `<input>`, a handful of layout rules: max-width, padding, font) can likely be done in **under 400 bytes** of CSS. This is a real visual downgrade (loses the "app-like" polish) — again a product tradeoff to confirm with the user, not something to silently ship.

3. **Do NOT serve CSS/JS as separate device-filesystem assets for the setup page.** This was raised as an option in the earlier comparison report but doesn't actually help here: a client hitting the setup AP for the first time still needs to fetch that separate `.css`/`.js` file from the Pico itself (no browser cache warm yet, single-visit flow), so it's the same total bytes served, just as two requests instead of one — plus it adds a second route/response path in the already-fragile setup HTTP surface (more code, more state, no memory win, since the file still has to be built into a response string/bytes in RAM once either way). This only pays off for repeat-visit pages, which is recommendation B below.

## Recommendation B — Login/settings pages: static assets + optional CDN, since real internet exists here

1. **Move `_CONFIG_CSS`, `_LOGIN_JS`, `_SETTINGS_JS` (currently duplicated between `page_login_content.py` and `page_settings_content.py` — same CSS literal copy-pasted in both files today) into one shared static asset served from the device filesystem** as `/static/config.css` and `/static/config.js`, with a `Cache-Control: max-age=<large>` response header. A user's browser fetches these once on first login, then reuses the cached copy for every subsequent settings visit — real bandwidth/CPU/heap win on the device for anything past the first request, since the device never has to rebuild+resend that string again within the cache lifetime. This also fixes the CSS duplication (one file, not two copies) — a maintenance win independent of memory.
2. **CDN is viable but not obviously worth it.** A generic lightweight CSS framework (e.g. Pico.css, Water.css — classless frameworks that need zero custom CSS to look reasonable) could replace `_CONFIG_CSS` entirely with a single `<link href="https://cdn.jsdelivr.net/...">` tag, cutting the device's own CSS to near zero for these two pages. But: this makes the admin config UI's *availability* depend on an external CDN being reachable from the user's home network at the moment they want to check their device settings — a real, if small, new failure mode (CDN down, DNS blocked, no internet that day) for a page whose whole job is *local* device administration. Recommend: **use recommendation B.1 (self-hosted static asset, cached) instead of a CDN** — same byte-size win, zero external dependency risk, consistent with the fact this is a local-network admin tool. If the user wants the CDN route anyway for faster initial styling, jQuery specifically is not needed at all here (no page currently does DOM manipulation heavy enough to justify jQuery's ~30KB+ payload over the CDN) — a classless CSS-only framework covers the actual need and is a fraction of jQuery's size.
3. Server-side change needed to support B.1/B.2: a new small static-asset route (`GET /static/<name>`) in `router.py`, reading the file once from device flash and streaming it — this is new code, should be scoped as its own small task alongside whichever page-shrink work is approved.

## Summary table

| Page | CDN viable? | Recommended action | Expected size cut |
|---|---|---|---|
| `page_setup_content.py` (setup AP) | **No** — no internet route in AP mode | Cut client-side JS state machine to plain server-rendered form; strip CSS to functional minimum | ~4.3KB JS → <1KB; ~1.8KB CSS → <0.4KB |
| `page_login_content.py` | Yes | Move shared CSS/JS to one cached static asset (dedupes today's copy-paste) | Removes duplicate ~1.8KB CSS copy |
| `page_settings_content.py` | Yes | Same static asset as login | Removes duplicate ~1.8KB CSS copy |

## Open questions for Minh before implementation

1. OK to drop the live no-reload SSID rescan / inline connect-status banner on the setup page in favor of full-page-reload navigation? (Biggest single JS cut, but a real UX change.)
2. OK to visually simplify the setup form (native controls, minimal styling) vs. the current custom-styled mobile-app-like look?
3. Self-hosted cached static asset (recommended) vs. external CDN framework for login/settings — any objection to adding a new `/static/<name>` route to support this?
