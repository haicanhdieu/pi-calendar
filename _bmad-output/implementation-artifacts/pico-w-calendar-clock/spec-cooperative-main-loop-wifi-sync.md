---
title: 'Synchronize Wi-Fi and NTP from the cooperative main loop'
type: 'bugfix'
created: '2026-09-06'
status: 'in-review'
route: 'dispatch'
baseline_commit: '6f9dce5c3d33cd27a7ea01235cfb6d19ed5f6842'
review_loop_iteration: 0
context:
  - '{project-root}/docs/hardware_configuration.md'
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/architecture/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The calendar displays `UNSYNCED` despite valid device-local credentials. Its NTP code performs WLAN operations in a second-core `_thread`, unlike the known-working feeder firmware, which runs WLAN association cooperatively on the main event loop. On the connected Pico, the threaded path never associates.

**Approach:** Replace the second-core network worker with a device-only, tick-driven coordinator running from the same main loop as the App. It will associate once, poll association and NTP response without blocking display updates, then publish the same bounded `SyncResult` consumed by the existing App.

## Boundaries & Constraints

**Always:** Preserve the App's pure import boundary and existing `SyncResult` acceptance rules; only the device coordinator may import `network` or `socket`. Keep credentials in device-local `secrets.py`, never logs or tracked files. Run every display/App iteration at its existing short cadence while Wi-Fi/NTP is pending. Use wrap-safe deadlines and exactly one terminal result per command. Retain current TFT pins, SPI configuration, views, RTC ownership (App alone writes UTC), and the staged display-repair changes. After implementation, deploy `main.py` and the changed `src/` files plus the existing device-local secrets to the connected Pico without deleting unrelated files.

**Never:** Do not start `_thread`, use blocking WLAN waits, use `ntptime.settime()`, make DNS, UDP receive, or sleep stall the render loop, or change the router/credentials as a workaround. Do not change the hardware configuration or flash MicroPython.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid Wi-Fi + NTP | Idle mailbox command; visible AP; valid credentials | Coordinator starts association once, accepts NTP response, publishes success; App writes RTC and removes `UNSYNCED` | No display-loop pause beyond one tick |
| Association pending | WLAN connects slowly | Each coordinator tick polls only; App Clock/Calendar continues to redraw | Deadline publishes one `wifi_fail`/`deadline` result |
| Invalid/missing credentials | Empty or missing device secrets | No WLAN call with blank values; App remains usable and unsynced | One `wifi_fail` result, retry follows configured cadence |
| DNS/UDP failure | Associated WLAN but lookup/send/receive fails or response is invalid | Pending socket work is closed; App keeps rendering | One terminal `dns_fail` or `ntp_fail` result |
| Stale/expired command | Deadline passes before success | Coordinator closes pending work and publishes no successful time | Existing App expiry gate rejects it and remains unsynced |

</frozen-after-approval>

## Code Map

- `main.py` -- Current composition imports `_thread`, constructs `NetworkWorker`, calls `worker.start()`, then blocks in `App.run_forever`; replace with the single cooperative App/coordinator loop.
- `src/app.py` -- Pure single writer already owns command enqueue and result application; reuse unchanged or only remove obsolete lock plumbing without importing device/network modules.
- `src/device/network/worker.py` -- Second-core loop that invokes the current blocking `NtpOps.run`; remove it from the production composition, leaving legacy proof code only if tests still require it.
- `src/device/network/ntp_ops.py` -- Current WLAN wait, DNS, and blocking UDP implementation; extract/reuse validation and NTP packet parsing only where it supports non-blocking coordinator operations.
- `src/device/network/mailbox.py` -- Reuse capacity-one command/result protocol without a lock because App and coordinator execute sequentially on core 0.
- `src/device/network/coordinator.py` -- Create device-only state machine with injected WLAN/socket/ticks/secrets seams; sole owner of asynchronous association and UDP lifecycle.
- `tests/test_app_sync.py` and new coordinator tests -- Existing pure App/mailbox assertions; extend with one-tick progression, single association call, deadline/failure cleanup, and App result integration.
- `/Users/minhtrucnguyen/working/ntm/feeder/wifi.py` -- Known-working reference: WLAN operation is invoked on the main loop and yields while association is pending; do not import it into this repository.

## Tasks & Acceptance

**Execution:**
- [x] `src/device/network/coordinator.py` -- Add injectable cooperative WLAN/NTP state machine with bounded, non-blocking socket polling -- moves radio I/O off core 1 without freezing display.
- [x] `src/device/network/ntp_ops.py` and `src/device/network/worker.py` -- Reuse or narrow protocol helpers; remove threaded/blocking execution from production path -- prevents the demonstrated association regression.
- [x] `main.py` -- Compose mailbox, coordinator, and App in one short tick loop; remove `_thread`/worker setup -- makes device ownership explicit.
- [x] `src/app.py` and tests -- Preserve pure App command/result semantics and eliminate obsolete lock dependency only if it no longer serves a caller -- retain single RTC writer and host compatibility.
- [x] `tests/test_network_coordinator.py` and existing sync tests -- Cover every matrix row and ensure no coordinator tick performs a wait loop -- host proof of responsive sequencing.
- [ ] Connected Pico W -- Deploy changed firmware plus existing secrets, reset, and verify a successful NTP sync clears `UNSYNCED` while Clock continues rendering -- on-device outcome.

**Acceptance Criteria:**
- Given valid credentials and an available access point, when the device boots, then its coordinator associates and synchronizes the RTC from NTP without any `_thread` WLAN/NTP execution, and the displayed `UNSYNCED` badge clears.
- Given a pending or failed network operation, when App iterations run, then Clock/Calendar deadlines and one-second redraws continue within their normal loop cadence.
- Given a failed, malformed, stale, or expired sync command, when the coordinator completes it, then it produces at most one terminal failure result, closes resources, and never writes the RTC directly.
- Given the production composition, when static host checks run, then pure modules remain free of `machine`, `network`, `ntptime`, `_thread`, and device imports.

## Implementation Notes

- Host implementation is complete: the coordinator and App run sequentially on core 0, and the loop ticks the coordinator before App so a pre-deadline response is consumed in the same iteration.
- The connected Pico received the changed firmware paths and reset reached the application-loop serial checkpoint, but physical NTP success and the TFT's `UNSYNCED` badge removal still require direct display observation. The connected-device task intentionally remains unchecked.

## Spec Change Log

## Review Triage Log

- `high` — `main.py` runs `app.step()` before `coordinator.tick()`, so a response published just before a command deadline is consumed on the next iteration after the App expiry gate and is discarded. Route: patch; run the coordinator first.
- `medium` — `coordinator.py` treats every `OSError` from `recvfrom()` as a temporary would-block condition, leaving permanent socket failures open until the deadline. Route: patch; distinguish would-block errno values and terminally fail other errors.
- `medium` — `coordinator.py` accepts a syntactically valid NTP datagram from any sender, allowing a local-network source to set the RTC. Route: patch; require the configured endpoint.
- `medium` — `coordinator.py` accepts non-server NTP packet modes, despite the invalid-response requirement. Route: patch; require a server response mode before timestamp parsing.
- `false` — Association polling does not inspect `WLAN.status()`, but the frozen matrix explicitly permits `wifi_fail` *or* `deadline` while association is pending; the deadline guard applies before each state transition, so the claimed indefinite command does not occur.
- `medium` — No test protects permanent UDP receive errors from being treated as would-block. Route: patch with the corresponding coordinator behavior test.
- `medium` — No test rejects wrong-source or non-server-mode NTP packets, which the current coordinator accepts. Route: patch with response-validation tests.
- `medium` — App and coordinator tests are isolated and do not prove their loop handoff writes RTC/trust after a real coordinator success. Route: patch with an ordered integration test and production-order assertion.
- `high` — The edge-case review independently confirms that the App-before-coordinator order causes timely final-cadence successes to be rejected as expired. Route: patch; same root cause as the first finding.
- `medium` — The edge-case review independently confirms permanent receive `OSError` is not terminal. Route: patch; same root cause as the second finding.
- `medium` — The edge-case review independently confirms non-server NTP modes are accepted. Route: patch; same root cause as the fourth finding.
- `medium` — The production loop is not dynamically executed by tests, so removal or misordering of coordinator work can leave the textual no-thread assertion passing. Route: patch with a host loop-order/integration proof.
- `medium` — A never-associated WLAN has no deadline regression test, although the implementation's top-level expiry guard currently handles it. Route: patch with an explicit pending-association deadline test.
- `medium` — Socket setup/send failures have terminal cleanup behavior but no regression test. Route: patch with a failing-send fake.

## Design Notes

The feeder proves association works when `network.WLAN` remains on the main execution path. The coordinator preserves the calendar's result boundary but changes execution ownership: App enqueues and consumes results, while sequential core-0 coordinator ticks own device I/O. NTP should use a configured numeric server address or an asynchronous lookup path so no synchronous DNS call can halt rendering; UDP receive must be non-blocking and polled until its command deadline.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: complete host suite, including coordinator matrix tests, passes.
- `mpremote connect /dev/cu.usbmodem1101 fs cp -r src/* :src` and `mpremote connect /dev/cu.usbmodem1101 fs cp main.py :main.py` -- expected: changed firmware paths deploy without deleting device files.
- `mpremote connect /dev/cu.usbmodem1101 reset` -- expected: device Clock starts, receives NTP time, and removes `UNSYNCED`.

**Manual checks (if no CLI):**
- Observe the connected TFT through boot and its first 15 seconds: it must keep rendering during sync and then show a real time/date without the orange badge.
