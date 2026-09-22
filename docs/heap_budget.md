# Heap budget

The Pico W runs this firmware in a 179,328-byte GC heap. That number is the
whole constraint: a build that exceeds it boots and renders fine, then fails
the first time a browser asks for the settings page, with `Empty reply from
server` as the only symptom.

## Why the heap fills up

MicroPython does not execute `.mpy` files from flash. Importing a module copies
its bytecode onto the heap and builds a module dict, a function object per
function, and an object per constant. Modules are never garbage collected, so
**everything imported at module scope stays resident for the device's entire
uptime.**

Two consequences drive every decision here:

1. **The resident set is what matters, not file size.** A module imported
   inside a function costs nothing until that function runs. That is why the
   station web surface (`src/device/web/*`, `src/provisioning/session.py`,
   `kdf_job.py`) is imported lazily — it only has to exist while serving.
   Lazily, though, is not the same as *never*: a module imported inside a
   route handler is resident from the first request that reaches it and is
   never given back. See "The boot-mode split" below.
2. **Data written as many small literals costs far more than the data.**
   `font.py` stored 41 glyphs as tuples of seven `"01010"` strings: roughly 400
   separate GC objects, 24,544 bytes, pinned from boot. The identical pixels as
   one packed `bytes` blob cost 1,632 bytes — a 93% reduction with no change to
   what is rendered.

The second point also explains why `gc.collect()` never helped. These objects
are all *live*; there is nothing to collect. And MicroPython's collector is
mark-and-sweep, not compacting, so a heap holding ~1,800 one-block objects has
free bytes scattered between them and no contiguous run big enough to load
another module.

## The boot-mode split

Trimming the resident set eventually ran out of room: the clock stack and the
whole admin site simply do not both fit. Issue #2 was the proof — every
`GET /settings/add` answered `503`, with about 2KB of device heap free at the
moment the request needed to import the alert editor.

So the device no longer tries. It boots into exactly one of two modes, and the
two stacks are never live together:

| | resident | HTTP presence |
|---|---|---|
| clock mode (`src/device/clock_mode.py`) | App, views, compositor, touch | `src/device/knock.py` only |
| config mode (`src/device/config_mode.py`) | settings store, display, alert scheduler | the full admin site |

`main.py` owns only the bring-up both modes need, then imports one of them.
Clock mode's entire web surface is a listening socket that answers any
connection with one fixed interstitial, writes `config.CONFIG_MODE_FLAG_PATH`
and resets. Config mode deletes that flag **as its first action** — on entry,
never on exit — so a crash there returns the device to the clock rather than
wedging it in a reboot loop. The session ends on the settings page's "Return
to clock" link, on `config.CONFIG_MODE_IDLE_MS` without a request, or when an
alert comes due (clock mode owns the buzzer and the dismiss surface).

Measured effect, in simulation, with the whole authenticated request path
resident: free heap while serving went from 4,480 to 50,400 bytes, and the
4096- and 8192-byte contiguous probes from `fail` to `ok`.

Two traps found while building it, both worth knowing before touching this:

- **`sys.modules.pop()` alone frees nothing.** The parent package still holds
  an attribute reference to the submodule. Purging measured 5,056 → 5,024
  bytes; adding `delattr(parent, leaf)` made the same purge 4,064 → 18,560.
- **Do not import anything from `src/device/web/` in clock mode.** That
  package's `__init__` exports `SetupHttpServer`, so a single import from
  inside it drags the whole bounded HTTP server in — measured at 17,696 bytes
  of simulated heap. That is why `knock.py` lives in `src/device/`.

## The gates

Run everything:

```bash
python -m tools.hostsim
```

`tools/deploy.py` runs this automatically and refuses to deploy on a breach.
`--skip-memory-gate` overrides it, for deliberately flashing a diagnostic
build.

### 1. Structural (always runs, in `pytest`)

`tests/test_memory_budget.py` parses the source and fails on:

- a module-level collection holding more than
  `budgets.MAX_STRING_LITERALS_PER_TABLE` string literals — the `font.py`
  pattern;
- any station web module reachable from `main.py` through module-scope imports,
  which would pin it from boot;
- `src/device/web/` importing `machine` or `network`, which would make the web
  surface untestable on the host.

Both resident sets are *derived*, not hardcoded: `tools/hostsim/graph.py` walks
module-scope imports from `main.py` plus the mode entry module — `clock_mode.py`
for a clock boot, `config_mode.py` for a config boot. Moving a lazy import to
module scope therefore trips the gate on its own, and so does letting a clock
module leak into config mode's closure or vice versa.

`STATION_WEB_MODULES` lists what a browser makes resident. It must include the
modules imported *inside route handlers* — `settings_post`, `alert_route`,
`alert_validation`, `page_alert_editor`, `postpone_route`, `kdf_job`. Leaving
them out is what let the gate pass green for months while the device answered
503 to every `/settings/add`: the simulation was modelling a device that did
not exist.

### 2. Compiled size (needs `mpy-cross`)

Per-module and per-group ceilings on `mpy-cross` output. A proxy for heap cost
— the heap holds that bytecode plus object overhead — that is cheap enough to
run on every commit.

### 3. Heap simulation (needs a MicroPython interpreter)

The real fix for the diagnosis problem. It stages exactly what `deploy.py`
pushes, imports it under MicroPython with a capped heap, and reports where a
`MemoryError` lands — in about a second, with no USB cable.

Build the interpreter once:

```bash
tools/hostsim/build_micropython.sh        # defaults to v1.20.0
```

The version must match the flashed firmware, because the simulation loads the
same `.mpy` files the device does and MicroPython rejects a `.mpy` whose format
version it does not implement. Check both:

```bash
mpremote connect /dev/cu.usbmodem101 exec "import sys; print(sys.implementation)"
mpy-cross --version
```

## Reading the simulation honestly

Two limits, both of which make it **conservative** rather than optimistic:

- It is a 64-bit host build. Pointers are twice the RP2040's width, so the same
  modules occupy more heap. `SIM_HEAP_SIZE` is calibrated to 200k for this
  reason: that is the smallest simulated heap which completes the work the
  device completes in 179,328 bytes. At the device's literal 179k, hardware
  that serves correctly still fails in simulation.
- There is no CYW43 driver, so Wi-Fi association and DHCP buffers are absent.
  Real devices have less headroom than the simulation suggests.

So: the simulation failing does not prove hardware fails, but it is the signal
to fix something. The simulation passing is necessary, not sufficient —
hardware remains the final authority. It reproduced the original bug exactly
(same failing module, 1,822 one-blocks against the device's 1,803) and
confirmed the fix, which is what it is for.

## Techniques that worked

| Change | Before | After |
|---|---|---|
| `font.py` glyph table → one `bytes` blob | 24,544 | 1,632 |
| `clock_view.py` `_SS`/`_HH`/`_MON`/`_DOW` → packed strings | 16,448 | 9,536 |
| `calendar_view.py` `_MONTHS`/`_WEEKDAYS` → packed strings | — | — |
| boot-mode split (issue #2), free heap while serving | 4,480 | 50,400 |

Boot-resident total fell from 164,992 to 134,656 bytes in simulation (−18%),
one-block objects from 1,822 to 1,187, and the device went from `Empty reply
from server` to serving `/`, `/login` and `/settings` correctly.

The trade to understand: packed tables allocate one short-lived string per
lookup where the old tuples returned a pinned one. That is deliberate. A
transient object the collector reclaims immediately is cheap; a permanent one
crowding out a one-time 38KB burst is what broke the device.

## Techniques that do not apply

- **Freezing modules into firmware** is the textbook fix and would move all of
  this to flash. It is rejected here: the product ships to users who will not
  reflash their Pico. Stock MicroPython, filesystem-only deploys.
- **`gc.collect()` / `gc.threshold()` tuning.** The resident objects are live.
- **Shrinking the display driver's per-call allocations.** Worth doing on its
  own merits, but measured against this bug it changed nothing: the
  fragmentation is present within seconds of boot, before the render loop has
  run enough to cause it.
