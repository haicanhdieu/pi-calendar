# Settings-page heap-fragmentation: attempts log (2026-09-14, live-device session)

Context: `spec-cannot-access-settings-page-after-boot-pi.md` (deferred entry:
"Confirmed heap-fragmentation root cause..."). This session tried to close
that deferred item on real hardware. It did not succeed; recorded here so
the next attempt doesn't repeat the same three things.

## The problem (unchanged from the spec)

Browser requests to `http://192.168.1.32/` and `/settings` still get
`Empty reply from server` (fast, clean close -- not a hang). Root cause:
`SessionTable()` construction (`src/provisioning/session.py`) throws
`MemoryError` on the first real station request because the heap is
fragmented into ~1800+ tiny 1-2 block allocations with no contiguous run
big enough to load the module. `gc.collect()` doesn't help (mark-sweep,
not compacting).

## Attempt 1: eager-import `session.py` in the existing asset-warmup block

**Where:** `src/device/network/coordinator.py`, `_tick_station_config`'s
`if not self._station_assets_ready:` block -- the same place that already
successfully imports `page_login_content`, `page_settings_content`,
`pages`, `router` on the first tick after the listener comes up.

**Hypothesis:** that early tick has proven headroom (confirmed via device
capture: 63744 -> 48272 bytes free, no failure) for the existing 4
modules; importing `session.py` there too (module import only, not
`SessionTable()` construction, to preserve the
`test_login_and_unknown_routes_do_not_allocate_sessions` contract) would
front-load the expensive part before fragmentation sets in.

**Result: FAILED on real hardware.** Flashed and captured serial:
```
web_heap station_asset_before 48976
web_heap station_asset_fail 46576
App loop: MemoryError, recovered   (repeating, every tick)
```
Reproduced the exact regression documented in the spec's Handoff as
"tried and reverted" (eager import at `__init__`): the *display* render
loop started throwing `MemoryError` on every tick. This is a second,
independent confirmation that this specific timing point does not have
spare headroom for one more module -- it's already at capacity for the 4
modules it currently loads.

**Reverted.** `git checkout` on `coordinator.py`, reflashed the known-good
build, confirmed stable (clean close, no error storm) before continuing.

## Attempt 2: eliminate per-`fill_rect` heap churn in the display driver

**Where:** `src/device/display/ili9341.py`. `fill_rect` allocated a fresh
`bytes` object every call (`row = bytes((hi, lo)) * (x1-x0+1)`), and
`set_window`/`_command` allocated 4 more small `bytes` objects per call
(command byte, two 4-byte CASET/PASET coordinate buffers). `draw_glyph`
(`src/device/display/font.py`) calls `fill_rect` once per lit pixel in a
5x7 bitmap -- roughly 15-20 times per character. The clock redraws every
`CLOCK_REDRAW_MS` (1000ms) for the device's entire uptime.

**Hypothesis:** this is the actual source of the ~1800 one-block / ~270
two-block allocations seen in the `micropython.mem_info(1)` dumps (sizes
match: `scale=1` glyphs -> 2-byte rows -> 1 GC block; `scale=9` clock
digits -> 18-byte rows -> 2 GC blocks). Hundreds of these tiny
allocate-then-discard cycles per second, forever, is exactly the pattern
that fragments a non-compacting mark-sweep heap.

**Fix applied:** preallocated reusable buffers (`_cmd_buf`, `_caset_buf`,
`_paset_buf`, `_row_buf`) on the `ILI9341` instance; `fill_rect` and
`set_window` now write into these in place and pass a `memoryview` slice
to `spi.write()` instead of allocating a new object every call. This
change is real and kept (see below) -- it is not device-only-untestable
in principle, but the file imports `machine.Pin` so no host test exercises
it; correctness was checked by reasoning plus a live visual check (clock
still renders correctly on the physical screen after flashing).

**Result: did NOT fix the settings-page failure.** Flashed, replugged,
captured serial on the very first browser request after boot (~8s post-
boot, only a handful of redraw ticks elapsed):
```
GC: total: 179328, used: 131520, free: 47808
No. of 1-blocks: 1803, 2-blocks: 263, max blk sz: 242, max free sz: 337
```
Compare to the original (pre-any-fix) baseline: `1825` one-blocks, `max
free sz: 361`. **Essentially unchanged** (1825 -> 1803 is noise-level;
`max free sz` actually got slightly *worse*, 361 -> 337). If glyph
rendering were the dominant fragmentation source, a request this early
(only ~8 redraw ticks elapsed) should have shown a much smaller block
count than the baseline captured after much longer uptime in the original
interactive session -- it didn't.

**Conclusion: the display-driver churn is not the (or not the dominant)
cause.** The fragmentation is present within seconds of boot, before the
render loop has done enough work to plausibly explain ~1800 allocations
on its own. Likely candidates not yet investigated: Wi-Fi driver internal
buffers during STA association/DHCP, MicroPython's own `.mpy` module
loading during boot, or the mailbox/network-worker plumbing constructed
in `main.py` before the app loop starts.

**Kept, not reverted:** the `ili9341.py` buffer-reuse change is a real,
independent improvement (removes real per-call heap churn, verified safe
via full host suite pass + live visual check) even though it didn't fix
this bug. It is currently uncommitted in the working tree.

## Attempt 3: capture `boot_pre_loop` heap snapshot (incomplete)

Tried twice to capture a `micropython.mem_info(1)` dump immediately after
"App loop starting" -- i.e. right before the render loop or any station
work begins -- to see whether the ~1800-block fragmentation is already
present at that exact point (which would conclusively rule out the render
loop and point at boot-time WLAN/module-load work instead). **Both
capture attempts came back empty** -- the passive serial reader's
reconnect-after-replug window (opens the port a few hundred ms after
`/dev/cu.usbmodem101` reappears) missed the burst of boot-time prints
both times. Not resolved before the session ended. This is the next
concrete diagnostic step: get that one snapshot, since it directly
answers whether the render loop matters at all here.

## What to try next (not yet attempted)

1. **Get the `boot_pre_loop` snapshot** (see above) -- settles whether
   render-loop churn is relevant at all before spending more time on it.
2. **Profile Wi-Fi association / boot-time allocations** specifically,
   since the fragmentation appears to already exist within ~8s of boot,
   before more than a handful of render ticks have run.
3. Do **not** repeat: eager-importing `session.py` at either `__init__`
   or the asset-warmup tick -- both are now confirmed, on real hardware,
   to break the display loop. That door is closed until something else
   changes the memory budget at that point in boot.

## New data point (2026-09-21, live-device E2E session)

While building a live-device E2E suite for the settings page, found the
same failure class hits a *different* first-use import than `session.py`:
the first request that renders the alert-editor inline form (either a
rejected `add` that re-shows the editor with an error banner, or
`GET /settings/edit/<id>`) reliably 503s with `web_request_memory` on a
freshly booted device -- confirmed via passive serial capture with a
temporary `sys.print_exception` added to `server.py`'s `_read_client`
(reverted before commit; not left in the tree). That request path lazily
imports `src/device/web/page_alert_editor.py`.

Separately (and unrelated to the fragmentation itself), that same code
path had a real, deterministic bug: `page_settings_content.py` used
`__import__("src.device.web.page_alert_editor", fromlist=["alert_editor_html"])`
to do the lazy import. MicroPython's built-in `__import__` does not accept
`fromlist` as a keyword argument (`TypeError: function doesn't take
keyword arguments`) -- CPython's does, so this was invisible to every host
test and only surfaced on real hardware. Fixed by replacing both call
sites with plain `from ... import ...` statements (verified working
on-device via `mpremote exec` before and after). Also added
`page_alert_editor.py`, `alert_route.py`, `alert_validation.py`,
`postpone_route.py`, and `settings_post.py` to `tools/deploy.py`'s
`PRECOMPILE` list, matching their sibling web modules -- they had been
missing since the alert feature was added.

The `__import__` bug was 100% deterministic and is now fixed and verified
gone (confirmed via `mpremote exec` reproducing the exact render call
directly). The `MemoryError` on the same request is the pre-existing,
still-unresolved fragmentation issue described above.

**Follow-up same session, broader finding:** after fixing the
`__import__` bug, found a second, unrelated, equally deterministic
MicroPython/CPython builtin gap on the very next request in this flow:
`alert_route.py`'s `edit_alert` used
`next((i for i, alert in enumerate(alerts) if ...), None)` --
MicroPython's built-in `next()` does not accept the CPython two-argument
default form (`TypeError: function takes 1 positional arguments but 2
were given`). Fixed with an explicit loop; verified via `mpremote exec`.
No other `next(iter, default)` or `__import__(..., fromlist=...)` call
sites exist anywhere in `src/` (grepped project-wide).

With *both* of those real bugs fixed, retesting still showed MemoryError
on early station requests -- but not narrowly scoped to the alert-editor
import as first suspected. Repeated clean-boot trials showed a plain
`add` (no editor render at all) fail on one boot and succeed on another;
retrying the exact same `edit` request that MemoryError'd on one boot
sometimes MemoryError'd again and sometimes didn't on the next boot. This
reframes the issue: it is not "importing module X always fails," it's
"the first few station HTTP requests after boot have some probability of
MemoryError, regardless of which handler they hit" -- consistent with a
genuinely fragmented heap rather than one under-provisioned import.
Precompiling `page_alert_editor.py`, `alert_route.py`,
`alert_validation.py`, `postpone_route.py`, and `settings_post.py` to
`.mpy` (they were missing from `tools/deploy.py`'s `PRECOMPILE` list
since the alert feature was added) did not resolve it.
`tests_e2e/test_alerts_business_e2e.py` documents this and sweeps any
stray alerts a mid-run MemoryError leaves behind at teardown, since a
"failed" mutating request is not proof nothing was persisted (a
MemoryError can strike after `store.commit()` but before the response
finishes rendering).

## Repo state at end of session

- `src/device/display/ili9341.py` -- buffer-reuse fix, uncommitted,
  real improvement, does not fix the settings-page bug.
- `src/device/network/coordinator.py`, `src/config.py`, `main.py` --
  reverted to the last committed (`done`) state; no experimental code
  left in the tree.
- Device is flashed with the `ili9341.py` fix + the previously-committed
  `close_clients()` fix; `WEB_HEAP_CHECKPOINTS` is back to `False` on the
  committed source (the device itself may still be running whatever was
  last flashed -- reflash to sync if needed).

---

## Attempt: heap ballast (issue #2, phase 1) — FAILED, reverted

Reserve a contiguous `bytearray(16384)` at boot while the heap is still
unfragmented, release it just before the station web imports, on the theory
that the failure was a heap with free bytes but no contiguous run.

It changed nothing on the device, and the simulation says exactly why: with
the alert request path resident, free heap is 4,128 bytes with the ballast and
4,128 bytes without it — byte for byte identical, 4096-byte contiguous probe
failing in both. A ballast relocates one run; it does not create heap. The
shortfall here was **total free heap**, not contiguity alone, so this was
aimed at the wrong quantity. Reverted in full.

## Root cause, finally measured

`GET /settings/add` failed 100% of the time on the bench unit, not
intermittently — earlier runs looked probabilistic because `kdf_job` becomes
resident at login and pushes the following request over the edge.

Serial capture at the moment of failure: `web_request_memory` then `web_asset`,
i.e. a real `MemoryError` inside `_read_client`'s dispatch, answered by
`server.py`'s fixed `503 Service temporarily unavailable`.

Simulated free heap, measured in stages (64-bit sim; device is roughly half):

| resident | free | contiguous |
|---|---|---|
| boot + modelled web set | 21,472 | 8192 ok |
| + `kdf_job` (after login) | 16,320 | 8192 ok |
| + alert request path | **4,480** | **4096 fail** |

The alert request path — `settings_post`, `alert_route`, `alert_validation`,
`page_alert_editor`, `postpone_route` — was never in
`tools/hostsim/graph.py`'s `STATION_WEB_MODULES`, so the gate had been
modelling a device that does not exist. It is in there now.

## Fix: boot-mode split (issue #2, phase 2) — WORKED

The clock stack and the admin site never need to coexist, so they no longer
do. See `docs/heap_budget.md`, "The boot-mode split". Free heap while serving:
4,480 → 50,400 in simulation; on hardware, `GET /settings/add` went from 503 on
every single attempt to 200 on every attempt, including repeated add/edit
cycles after an alert exists — the exact sequence reported in the issue.
`tests_e2e/test_alerts_business_e2e.py` passes 6/6.

Two MicroPython traps worth not rediscovering:

- `sys.modules.pop(name)` alone reclaims nothing; the parent package keeps an
  attribute reference. With `delattr(parent, leaf)` the same purge went from
  5,024 to 18,560 bytes free.
- A socket accepted from a non-blocking listener is non-blocking too, and the
  first `send` to a browser raises `EAGAIN`. Treating that as failure made the
  knock listener reset the device with the interstitial never delivered.
