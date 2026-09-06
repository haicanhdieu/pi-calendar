# Technology Currency and Reality-Check Review — Post-Mailbox Final Gate

**Artifact reviewed:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-06  
**Verdict:** **PASS WITH MANDATORY FLASHED-DEVICE PROOF**  
**Severity summary:** 0 critical, 0 high

No critical or high technology-currency finding remains. AD-8's capacity-one,
two-slot mailbox closes the prior overwrite/backpressure ambiguity without
weakening the nonblocking render-loop boundary. The only material platform
uncertainty is MicroPython `_thread` stability on the flashed Pico W, and the
spine correctly treats that as an explicit assumption with a pre-FR-1 proof
gate and architecture-revision fallback.

## AD-8 mailbox assessment

The revised rule provides an internally consistent ownership protocol:

- App and the worker use separate capacity-one command and result slots under
  one lock.
- App enqueues only while the worker is idle and polls without blocking.
- The worker atomically consumes one command and publishes one terminal result
  only into an empty result slot.
- A result is never overwritten; saturation is a contract violation rather
  than an implicit drop policy.
- App consumes every result and cannot enqueue a retry until the prior result is
  consumed and the worker is idle.
- `command_id` plus expiry checking prevents a stale or late result from being
  applied to a newer synchronization attempt.
- Only App mutates RTC, trust, or `AppState`; the worker owns only network-local
  activity and mailbox publication.

This protocol fits the selected runtime. MicroPython v1.29.0's RP2 build enables
threads, exports `allocate_lock`, and is configured without a GIL, so explicit
locking is necessary and available. The capacity-one slots also provide a
concrete memory bound.

Primary evidence:

- [MicroPython v1.29.0 RP2 configuration](https://github.com/micropython/micropython/blob/v1.29.0/ports/rp2/mpconfigport.h)
- [MicroPython v1.29.0 RP2 build sources](https://github.com/micropython/micropython/blob/v1.29.0/ports/rp2/CMakeLists.txt)
- [MicroPython v1.29.0 `_thread` implementation](https://github.com/micropython/micropython/blob/v1.29.0/py/modthread.c)

## Blocking-network fit

The official `ntptime` implementation synchronously resolves DNS and waits for
UDP, while `ntptime.settime()` directly mutates `machine.RTC`. AD-8 now contains
both hazards: WLAN, DNS, and UDP work run only in the worker; bounded operations
must enforce the command deadline; and bundled `settime()` is forbidden. Even a
stalled network operation therefore cannot stall the App/render loop, although
the exact timeout and recovery behavior remains part of the mandatory device
proof.

Primary evidence:

- [Official MicroPython `ntptime` source](https://github.com/micropython/micropython-lib/blob/master/micropython/net/ntptime/ntptime.py)

## Experimental-status gate

MicroPython's v1.29.0 documentation explicitly calls `_thread` highly
experimental and says its API is not fully settled or documented. The spine
does not present it as stable: the Stack marks `[ASSUMPTION]`, and Deferred
blocks FR-1 implementation until the exact one-worker/two-slot mailbox passes a
flashed-device test. Failure requires revising AD-8 and may not be worked around
by moving blocking network work into App.

Primary evidence:

- [MicroPython v1.29.0 `_thread` documentation](https://docs.micropython.org/en/v1.29.0/library/_thread.html)

The device proof must cover successful and failed DNS/NTP paths, result-slot
contention, stale and expired results, retry sequencing, worker idle-state
transitions, soft reset, render continuity, and sustained memory/lock behavior.
That missing runtime evidence is not a spine defect because it is an explicit
go/no-go condition before dependent implementation.

## Version and source audit

- The official Pico W release index lists v1.29.0 as the current stable firmware
  and v1.30 artifacts as previews.
- The spine pins the library index, `_thread` documentation, and RP2 quick
  reference to v1.29.0.
- No `latest` documentation URL remains. The live firmware-download page is
  appropriately used only to check release currency; the selected release is
  fixed in the Stack.

Primary evidence:

- [Official Pico W firmware downloads](https://www.micropython.org/download/RPI_PICO_W/)
- [MicroPython v1.29.0 library index](https://docs.micropython.org/en/v1.29.0/library/index.html)
- [MicroPython v1.29.0 RP2 quick reference](https://docs.micropython.org/en/v1.29.0/rp2/quickref.html)

## Final disposition

| Concern | Status |
| --- | --- |
| Blocking network work on render loop | **Resolved:** isolated worker owns it. |
| Mailbox overwrite or ambiguous backpressure | **Resolved:** separate capacity-one slots and no-overwrite rule. |
| Retry racing an unconsumed result | **Resolved:** retry waits for result consumption and worker idle. |
| Late result restoring trust incorrectly | **Resolved:** ID match and expiry are mandatory; stale/expired attempts set `unsynced`. |
| Worker mutating RTC or product state | **Resolved:** App is sole writer; `ntptime.settime()` is forbidden. |
| `_thread` treated as proven/stable | **Resolved as gated assumption:** flashed-device proof is mandatory. |
| Unversioned platform documentation | **Resolved:** MicroPython sources are pinned to v1.29.0. |

**Gate result: PASS. No remaining critical/high findings.** The flashed-device
worker proof remains a mandatory implementation prerequisite; failure reopens
AD-8 rather than this gate silently accepting a blocking fallback.
