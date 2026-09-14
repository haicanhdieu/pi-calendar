# Pinned native-auth/firmware context: station HTTP fix (2026-09-14)

Source of truth for this fix: `_bmad-output/implementation-artifacts/touch-ui/spec-cannot-access-settings-page-after-boot-pi.md`
(see its "Handoff" section for full root-cause analysis, bisection method, and
device evidence). This file records only the pinned deployment/native-auth
facts that future wifi-config work should not have to re-derive.

## Firmware precompile change

`tools/deploy.py` `PRECOMPILE` now includes `src/provisioning/session.py`.

- Before this fix, `session.py` was the only module among its
  `src/provisioning/` siblings (`scan.py`, `validation.py`, `verifier.py`,
  `kdf_job.py`) shipped as source-compiled-on-device instead of precompiled
  `.mpy`. That asymmetry was real but was **not** the root cause of the
  station-HTTP failure (see below) -- keep the precompile fix regardless.
- Verified: 371/371 host tests pass with this change; confirmed on-device
  via flashed build (`uv run tools/deploy.py --port /dev/cu.usbmodem101`).

## Native-auth (session/login) heap-fragmentation finding

Confirmed via on-device `micropython.mem_info(1)`: constructing the
config-auth `SessionTable` (`src/provisioning/session.py`) on the first
station browser request fails with `MemoryError` because, by that point in
boot, the heap is fragmented into thousands of 1-2 block allocations (from
display/UI + network-worker churn) -- there is nominal free heap but no
single contiguous run large enough for the module/table allocation.
`gc.collect()` does not help (MicroPython's collector is mark-sweep, not
compacting).

This is **not yet fixed** -- it is an open architectural item. Do not
attempt an eager import of station web/session modules in
`NetworkCoordinator.__init__` or immediately after a
`self._mode = MODE_STATION_ONLINE` assignment as a fix without first
measuring free/contiguous heap at that exact point on a real device: an
earlier attempt at this (reverted) caused the display/UI render loop to
throw `MemoryError` on every tick instead. See the touch-ui spec's
"Recommended next steps" for the options considered.

## What *is* fixed and confirmed on-device now

`src/device/network/coordinator.py`: `http.close_clients()` added to the two
`_tick_station_config` failure branches (around the lazy station-asset
import) that were missing it while every structurally identical failure
branch elsewhere in the file already closed clients on failure -- so a
failed request no longer leaves an accepted browser socket open with no
response. A `gc.collect()` was also added immediately before `http.tick()`.
Net effect: the browser gets a fast, clean connection close instead of an
indefinite hang. The underlying `MemoryError` on `SessionTable()`
construction (native-auth) is unchanged and still occurs; settings therefore
still does not load until the fragmentation issue above is solved.
