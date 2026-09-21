"""Memory budgets for the Pico W build.

The device has a 179,328-byte GC heap.  Serving the station admin site means
the boot-resident module set and the whole station web chain have to be live
simultaneously, so the budgets below cap both halves with headroom.

Numbers were set from measurements taken while fixing the settings-page
``MemoryError`` (see ``docs/heap_budget.md``).  Tightening one after a real
reduction is welcome; raising one means the device got closer to the cliff, so
raise it deliberately and say why in the commit message.
"""

# Compiled-size budgets (``mpy-cross`` output, bytes).  A proxy for heap cost:
# the heap holds the same bytecode plus per-object overhead, so growth here is
# growth there.  Cheap to check and needs no MicroPython interpreter.
BOOT_RESIDENT_MPY_BYTES = 47_150  # Story 2.5 pending-state schema headroom
STATION_WEB_MPY_BYTES = 37_000  # measured 34,166
COMBINED_MPY_BYTES = 84_000  # measured 78,019

# Single-module ceiling.  `coordinator.py` is the standing outlier and is
# pinned separately so the general ceiling can stay meaningfully low.
MODULE_MPY_BYTES = 8_000
MODULE_MPY_BYTES_OVERRIDES = {
    "src.device.network.coordinator": 16_000,  # measured 14,758; split it to lower this
}

# Heap budgets, enforced by the MicroPython simulation when a matching
# interpreter is available (``tools/hostsim/build_micropython.sh``).
#
# The simulator is a 64-bit host build: pointers are twice the width of the
# RP2040's, so the same modules occupy more heap there.  Running it at the
# device's literal 179,328 bytes is therefore unfair -- hardware that serves
# the admin site correctly still fails in simulation.
#
# SIM_HEAP_SIZE is calibrated instead: 200k is the smallest simulated heap
# that completes the same work the device completes in 179,328 bytes (at 179k
# the simulation fails importing `src.provisioning.session`; at 200k every
# import and every contiguous-allocation probe passes).  Treat it as "the
# device's heap, expressed in 64-bit host terms".
#
# The margin at 200k is deliberately modest -- roughly 30KB free once
# everything is resident -- so that a real regression trips the gate rather
# than being absorbed by slack.
SIM_HEAP_SIZE = "200k"
SIM_BOOT_RESIDENT_BYTES = 112_000  # measured 103,648
SIM_MIN_FREE_AFTER_BOOT = 88_000  # measured 98,560

# Every probe size must succeed once all modules are resident.  The original
# bug was a heap with free bytes but no contiguous run, so total-free checks
# alone would not have caught it.
SIM_REQUIRED_CONTIGUOUS = (512, 1024, 2048, 4096)

# Guard against reintroducing the allocation pattern that caused the bug: a
# module-level collection of many small string literals becomes one pinned GC
# object per element.  `font.py` cost 24,544 bytes as 41 glyph tuples of seven
# strings each; packed into one `bytes` blob it costs 1,632.
MAX_STRING_LITERALS_PER_TABLE = 8
