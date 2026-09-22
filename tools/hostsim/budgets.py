"""Memory budgets for the Pico W build.

The device has a 179,328-byte GC heap.  It boots into one of two modes and
never both: clock mode runs the clock stack and no web stack, and config mode
runs the web stack and no clock stack (see ``src/device/config_mode.py``).
The budgets below therefore cap three things: each boot mode's resident set,
and the web chain that config mode loads on top of its own.

Numbers were set from measurements taken while fixing the settings-page
``MemoryError`` (see ``docs/heap_budget.md``).  Tightening one after a real
reduction is welcome; raising one means the device got closer to the cliff, so
raise it deliberately and say why in the commit message.
"""

# Compiled-size budgets (``mpy-cross`` output, bytes).  A proxy for heap cost:
# the heap holds the same bytecode plus per-object overhead, so growth here is
# growth there.  Cheap to check and needs no MicroPython interpreter.
BOOT_RESIDENT_MPY_BYTES = 50_500  # clock mode; measured 49,600
CONFIG_RESIDENT_MPY_BYTES = 26_000  # config mode; measured 24,836
# The web chain now includes the authenticated request path (settings POST
# handlers, alert editor, alert validation, postpone, KDF job).  Those were
# lazily imported and unmodelled before issue #2, which is exactly why a gate
# that passed could sit alongside a device that answered 503 to every
# /settings/add.
STATION_WEB_MPY_BYTES = 49_000  # measured 48,190
# Only config mode ever holds resident + web at once.
COMBINED_MPY_BYTES = 74_000  # measured 73,026

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
SIM_BOOT_RESIDENT_BYTES = 115_000  # clock mode; measured 113,600
SIM_MIN_FREE_AFTER_BOOT = 85_000  # clock mode; measured 88,608

# Config mode's own resident set, and the floor on what is left once the whole
# admin site -- request path included -- is resident on top of it.  That floor
# is the number issue #2 was really about: the device was serving requests with
# roughly 2KB of device heap left, so any page render tipped it into
# MemoryError.
SIM_CONFIG_RESIDENT_BYTES = 80_000  # measured 76,416
SIM_MIN_FREE_SERVING = 40_000  # measured 50,272; was 4,480 before issue #2

# Every probe size must succeed once all modules are resident.  The original
# bug was a heap with free bytes but no contiguous run, so total-free checks
# alone would not have caught it.
SIM_REQUIRED_CONTIGUOUS = (512, 1024, 2048, 4096, 8192)

# Guard against reintroducing the allocation pattern that caused the bug: a
# module-level collection of many small string literals becomes one pinned GC
# object per element.  `font.py` cost 24,544 bytes as 41 glyph tuples of seven
# strings each; packed into one `bytes` blob it costs 1,632.
MAX_STRING_LITERALS_PER_TABLE = 8
