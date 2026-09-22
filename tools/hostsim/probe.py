"""Runs inside MicroPython, inside the staged deploy tree.

Imports one boot mode's module set the same way and in the same order the
device does, and reports heap occupancy at each stage.  Output is one
``key=value`` line per fact so the host runner can parse it without depending
on MicroPython's formatting.

The runner invokes this twice, because the device never holds both boot modes
at once and neither can a faithful simulation:

``PHASE == "clock"``
    The clock-mode resident set on its own.  No web modules are loaded,
    because clock mode serves no admin site.

``PHASE == "config"``
    The config-mode resident set, then the whole station web chain on top of
    it -- including the authenticated request path, which is resident from the
    first browser request that touches it.  The contiguous probe runs here,
    where the device actually serves pages.

The module lists are written to ``_modules.py`` by the runner, which derives
them from the real import graph.
"""

import gc

import _modules


def _emit(key, value):
    print("%s=%s" % (key, value))


def _load(modules, stage):
    failures = []
    for name in modules:
        try:
            __import__(name)
        except MemoryError as exc:
            failures.append("%s: MemoryError %s" % (name, exc))
        except Exception as exc:  # noqa: BLE001 - reported, not handled
            failures.append("%s: %s %s" % (name, type(exc).__name__, exc))
        # Collecting once after the whole stage leaves every import's
        # compile-time garbage (parse buffers, temporary tuples) stacked up
        # at once, fragmenting the heap in a way a real boot never sees:
        # MicroPython's own allocation-threshold GC runs *during* this same
        # import sequence on hardware, not only after it finishes.
        gc.collect()
    _emit(stage + "_alloc", gc.mem_alloc())
    _emit(stage + "_free", gc.mem_free())
    for failure in failures:
        _emit(stage + "_failure", failure)
    return failures


def main():
    gc.collect()
    _emit("heap_total", gc.mem_alloc() + gc.mem_free())

    if _modules.PHASE == "clock":
        _load(_modules.BOOT, "boot")
        gc.collect()
        _emit("clock_final_free", gc.mem_free())
        return

    _load(_modules.CONFIG, "config")
    _load(_modules.WEB, "web")

    # A browser request needs a contiguous run for socket, parser and response
    # buffers after every module it touches is resident.  A heap that is merely
    # "free enough" in total can still fail here, which is the failure this
    # whole exercise was chasing.
    for size in _modules.CONTIGUOUS:
        try:
            buf = bytearray(size)
            del buf
            _emit("contiguous_%d" % size, "ok")
        except MemoryError:
            _emit("contiguous_%d" % size, "fail")
    gc.collect()
    _emit("final_free", gc.mem_free())


main()
