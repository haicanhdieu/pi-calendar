---
title: 'Synchronize Clock time without blocking the display'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: 'db52062701f8068c0ba794a01491fa0ef66b3c4d'
baseline_commit: 'db52062701f8068c0ba794a01491fa0ef66b3c4d'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md'
warnings:
  - oversized
deferred:
  - summary: >-
      socket.getaddrinfo in NtpOps has no bounded deadline; a hung DNS lookup can block the worker indefinitely.
    evidence: |-
      MicroPython v1.20 has no portable bounded-DNS API used here; pre/post deadline checks cannot interrupt an in-flight getaddrinfo. Settle by observing DNS hang behavior on-device or adding a platform-specific timeout if available.
    location: >-
      src/device/network/ntp_ops.py:_query_ntp
    severity: medium
  - summary: >-
      If the worker never publishes after take (infinite hang), App enqueue stays rejected while mailbox non-idle; soft_reset-on-expiry was not added because it cannot unstick a hung ops call.
    evidence: |-
      Edge claim of indefinite reject is true only under infinite worker hang (maybe-false for finite ops). Settle by confirming whether Pico W getaddrinfo/connect ever fail to return under bad network.
    location: >-
      src/app.py:_maybe_enqueue_sync
    severity: medium (unverified)
  - summary: >-
      main.py production composition (shared Mailbox + NetworkWorker.start + NtpOps) has no host test because main imports machine.
    evidence: |-
      Host suite covers App↔mailbox and NtpOps injectables only; device flash remains the composition proof path. Intent forbids claiming on-device NTP from host.
    location: >-
      main.py
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Stories 1.3–1.4 delivered a single-writer App and a proven AD-8 mailbox, but production never enqueues sync or applies NTP results—so the clock cannot regain trustworthy local time after Wi-Fi is available.

**Approach:** Wire App to the capacity-one mailbox (enqueue on due retry while idle; consume matching non-expired results), run real WLAN/DNS/UDP NTP only inside injectable worker ops, and let App alone write UTC via ClockPort and mark trust—never `ntptime.settime()`.

## Boundaries & Constraints

**Always:**
- App enqueues at most one `SyncCommand(command_id, deadline_ms)` while mailbox idle and result slot empty; worker alone owns WLAN, DNS, and UDP NTP.
- App accepts only matching, non-expired results; success → `ClockPort.set_utc` + trust `synced` + `utc_valid=True`; failed/expired/stale → trust `unsynced` (reuse `report_time_source_failure` path).
- Capacity-one protocol: never overwrite results; retry only after consume + idle; saturation → fatal diagnostic log.
- After every terminal consume (ok or fail), schedule next retry with configurable `NTP_RETRY_MS` (v1 = 3_600_000). Boot arms retry due immediately so the first attempt is not deferred an hour.
- Pure App/mailbox path stays free of `machine`/`network`/`ntptime`/`_thread` imports; inject mailbox + lock (+ optional sync gate). Credentials via existing `credentials_valid` / `secrets.py` (AD-9).

**Never:**
- Call bundled `ntptime.settime()`.
- Block the App/render loop on WLAN/DNS/NTP, or fall back to in-loop networking if the worker is busy.
- Let the worker touch RTC, TFT, or `AppState`.
- Claim on-device NTP success from host runs; host-test App↔mailbox with fakes/injectable ops.
- Change pins/SPI/MADCTL or replace the Story 1.4 proof harness path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Boot enqueue | retry due, mailbox idle, sync enabled | Non-blocking enqueue of bounded SyncCommand; worker leaves idle | Reject if busy/result occupied |
| Consume success | Matching non-expired `ok=True` + utc | App `set_utc`; trust synced; utc_valid True; re-arm retry with NTP_RETRY_MS | No error expected |
| Consume failure | Matching non-expired `ok=False` | Trust unsynced + diagnostic; no RTC write; re-arm retry | Soft fail |
| Stale/expired/mismatch | Wrong id or past deadline | Discard; trust unsynced; no RTC write | Soft fail |
| Slot occupied | Busy or unconsumed result | Enqueue rejected; no overwrite | Wait consume+idle |
| Saturation | Publish into occupied result | Fatal contract diagnostic; prior result kept | Log FATAL; do not crash App loop |
| Credentials invalid | `credentials_valid()` False at compose | No enqueue (or soft-fail already); stay unsynced | Soft fail, no boot crash |
| Interval | After any terminal consume | Next retry = ticks_add(now, NTP_RETRY_MS) | Configurable constant only |

</intent-contract>

## Code Map

- `src/app.py` (~L55–148) -- **Extend:** inject optional `mailbox`, `lock`, `sync_enabled` (default True). In `step`: (1) under lock `try_take_result` → `should_apply_result` → apply success/`report_time_source_failure`; track `_pending_command_id` + deadline for match/expiry; (2) when `retry_deadline` due and sync_enabled and enqueue succeeds, mint monotonic `command_id`, `deadline_ms=ticks_add(now, SYNC_COMMAND_DEADLINE_MS)`. Boot: set `retry_deadline=now` (immediate first attempt). Import `TRUST_SYNCED`, mailbox types only if kept out of purity ban—prefer duck-typed injectables so App never imports `src.device`. Reuse `report_time_source_failure`; on success set `trust=TRUST_SYNCED`, `utc_valid=True`, `sync_age_ms` (0 or ticks-based age). Keep purity: no `machine`/`network`/`ntptime`/`src.device`.
- `src/device/network/mailbox.py` -- **Reuse as-is:** `SyncCommand`/`SyncResult`/`Mailbox`/`should_apply_result`/`MailboxSaturationError`.
- `src/device/network/worker.py` -- **Reuse shell:** `NetworkWorker` + `set_ops`; lock only around take/publish.
- `src/device/network/ntp_ops.py` (new) -- **Create:** `NtpOps.run(command) -> SyncResult` owning WLAN connect (from `secrets`), DNS, UDP NTP query; return UTC `DateTime` on success; error_codes for wifi/dns/ntp/deadline; **never** call `ntptime.settime()`; never touch RTC/TFT/AppState. Prefer raw NTP packet or `ntptime` query-only if available without settime.
- `src/device/clock_port.py` -- **Reuse:** `set_utc` / `read_utc` (App-only writer).
- `src/config.py` (~L92–97) -- **Update comment:** `NTP_RETRY_MS` is production retry; keep `SYNC_COMMAND_DEADLINE_MS`; leave `NETWORK_PROOF_MODE` False.
- `src/credentials.py` / `secrets.example.py` -- **Reuse:** main gates `sync_enabled=credentials_valid()`; ops still read secrets for WLAN.
- `main.py` (~L21–64) -- **Compose:** keep proof gate; else create `Mailbox`, `_thread.allocate_lock()`, `NtpOps`, `NetworkWorker.start()`, pass mailbox/lock/`sync_enabled` into `App`.
- `tests/test_app_sync.py` (new) and/or extend `tests/test_app_loop.py` -- Fake mailbox/lock/ops + FakeClockPort: cover I/O matrix (enqueue idle, reject busy, apply success→set_utc+synced, fail/stale/expired→unsynced, retry interval, no `ntptime.settime`, purity of `app.py`).
- Continuity: `proof-1-4-network-mailbox.md` 9/9 PASS; do not re-run device proof as a gate for host completion. Architecture AD-3–AD-5, AD-8, AD-9.

## Tasks & Acceptance

**Execution:**
- [x] `src/app.py` -- Wire enqueue/consume under injected mailbox+lock; boot immediate retry; apply ClockPort + trust -- AD-8 App side
- [x] `src/device/network/ntp_ops.py` -- Real WLAN/DNS/UDP NTP ops returning SyncResult; never settime -- AD-8 worker ops
- [x] `main.py` (+ config comment) -- Compose mailbox, lock, worker, NtpOps, sync_enabled gate -- product boot path
- [x] `tests/test_app_sync.py` (and purity/loop asserts as needed) -- Cover I/O matrix + no settime + App purity -- host verification

**Acceptance Criteria:**
- Given Story 1.4's successful hardware proof, when App needs a sync attempt, then it non-blockingly enqueues one bounded SyncCommand(command_id, deadline_ms) only while the worker is idle, and the isolated worker alone owns WLAN, DNS, and UDP NTP operations.
- Given a terminal worker result, when App consumes it, then it accepts only the matching, non-expired result; successful UTC is written only by App through ClockPort and marks trust synced, while failed, expired, or stale results mark trust unsynced.
- Given the capacity-one command/result protocol, when a slot is occupied, then results are never overwritten, retry waits for prior-result consumption and worker-idle state, and saturation is logged as a fatal contract violation.
- Given a successful or failed attempt, when its next deadline is scheduled, then the default recurring interval is configurable and is one hour for v1; bundled ntptime.settime() is not called.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 18 findings — high 0, medium 11, low 2, false 4, maybe-false 1
- findings:
  - `[medium]` `[patch]` NtpOps recv timeout not clamped to remaining SyncCommand deadline — clamped `settimeout` to min(2s, remaining ms/1000) with 0.05s floor.
  - `[medium]` `[defer]` `getaddrinfo` has no deadline budget — platform limitation on MP 1.20; recorded in `deferred`.
  - `[medium]` `[patch]` Wi-Fi 12s + NTP 2s vs 15s command deadline leaves no margin — `_WIFI_CONNECT_BUDGET_MS` reduced to 10_000.
  - `[low]` `[reject]` Spec Code Map still says `_pending_command_id` vs `_inflight_id` — fix would edit this build's spec; Design Notes already use `_inflight_*`.
  - `[false]` `[reject]` Tasks `[x]` while sprint `in-progress` / empty triage — mid-workflow expected; triage/finalize set `done`.
  - `[medium]` `[patch]` Missing NtpOps `dns_fail` / `ntp_fail` host tests — added injectable FakeSocket cases in `test_app_sync.py`.
  - `[low]` `[patch]` Worker still logs `PROOF:WORKER_OPS_ERROR` — renamed to `WORKER_OPS_ERROR`.
  - `[false]` `[reject]` `sync_age_ms` stuck at 0 after success — AC allows 0 at apply; advancing age not required by this story.
  - `[low]` `[reject]` Worker started when `sync_enabled` False — harmless idle poll; credentials usually present; branch complexity not worth it.
  - `[medium]` `[patch]` NTP LI alarm / stratum 0 accepted — reject with `ntp_fail` before timestamp conversion.
  - `[medium]` `[patch]` Slot-occupied path only bare Mailbox — added App-level occupied-result enqueue reject test.
  - `[false]` `[reject]` `warnings: oversized` with empty deferred — oversized is a token-size warning, not postponed scope.
  - `[maybe-false]` `[defer]` Inflight deadline with no result → indefinite enqueue reject — true only if worker never publishes; deferred with unverified medium.
  - `[false]` `[reject]` `wlan.connect` blocks beyond deadline — code uses non-blocking connect + deadline-polled wait.
  - `[medium]` `[defer]` `getaddrinfo` hang (edge duplicate of blind-hunter DNS finding) — same deferred DNS budget item.
  - `[medium]` `[patch]` NTP stratum 0 / LI alarm (edge duplicate) — same LI/stratum reject patch.
  - `[medium]` `[patch]` Verification gap: NtpOps DNS/NTP soft-fail untested — same injectable tests as above.
  - `[medium]` `[defer]` Verification gap: `main.py` worker/NtpOps composition untested — deferred; device-only `machine` entry.

## Design Notes

- **Purity:** Keep `app.py` free of `src.device` imports by injecting mailbox/lock objects; production types come from `main.py` composition. Host tests pass the real pure `Mailbox` plus a fake lock.
- **Boot sync:** `boot()` sets `retry_deadline = now` (due immediately). After each applied/discarded terminal result, re-arm with `NTP_RETRY_MS`. Do not re-arm retry solely because the deadline fired without an enqueue attempt when the mailbox was busy—re-arm after enqueue attempt or after a skipped-gate tick so the loop does not spin every 10 ms; preferred: on due, try enqueue once; if rejected, leave deadline due (or short backoff) until idle+empty; on accept or sync_disabled skip, arm full `NTP_RETRY_MS`.
- **command_id:** Monotonic integer on App (`_next_command_id`), stored as `_inflight_id` + `_inflight_deadline` until consume.
- **NTP without settime:** Implement UDP NTP client returning epoch→DateTime fields; if using MicroPython `ntptime`, call only a query helper—never `settime()`.
- **Saturation:** Worker already sets `fatal` + logs; App need not halt—continue rendering; host tests assert prior result preserved.

## Verification

**Commands:**
- `uv run pytest` -- expected: all existing + new sync tests pass
- `uv run python -c "from src.app import App; from src.device.network.mailbox import Mailbox"` -- expected: imports without claiming device NTP

**Manual checks (if no CLI):**
- User may flash and observe sync on Pico W; agent must not invent device NTP results. Host fakes prove App/mailbox contract only.

## Auto Run Result

Status: done

Summary: Story 1.5 wires production App↔mailbox sync: boot-immediate enqueue, consume matching non-expired results, App-only `ClockPort.set_utc` + trust, real `NtpOps` (WLAN/DNS/UDP NTP, never `ntptime.settime()`), and `main.py` composition with credentials gate. Review patches tightened deadline margin, KoD/LI rejection, worker log label, and host NtpOps/App occupied-slot coverage.

Files changed:
- `src/app.py` — mailbox enqueue/consume under injected lock; boot immediate retry; trust/UTC apply
- `src/device/network/ntp_ops.py` — real NTP ops without settime; deadline-clamped recv; KoD/LI reject
- `src/device/network/worker.py` — product `WORKER_OPS_ERROR` log label
- `main.py` — Mailbox + lock + NtpOps + NetworkWorker composition; `sync_enabled`
- `src/config.py` — production NTP_RETRY_MS comment
- `tests/test_app_sync.py` / `tests/test_app_loop.py` — I/O matrix + NtpOps failure cases + purity
- `sprint-status.yaml` / this spec — story + epic-1 done

Review findings: patched 5 medium + 1 low; deferred 3 (DNS budget, infinite-hang maybe-false, main composition); rejected false/low as logged. Follow-up review recommended: true — multiple medium patches (deadline margin, KoD/LI, NtpOps tests); unverified residual risk is on-device DNS hang / composition under real Wi-Fi.

Verification:
- `uv run pytest` → 131 passed
- App/Mailbox imports OK
- No on-device NTP claimed from host

Residual risks: hung `getaddrinfo` can block the worker; flash + serial still needed to confirm real Wi-Fi/NTP on Pico W; `sync_age_ms` remains 0 after apply until a later story advances it.

Blocking condition: none

Note: commit skipped per orchestrator instruction — working tree left dirty for parent commit.
