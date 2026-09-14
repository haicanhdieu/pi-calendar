"""Memory budget gates for the Pico W build.

The device fits a 179,328-byte GC heap, and every module imported at module
scope stays on it for the whole uptime.  The settings page failed for weeks
because that resident set grew until the station web chain had no room left to
import, so these gates fail the build before a deploy can reintroduce it.

Three layers, cheapest first:

* structural -- no module-level table of many small literals, and no station
  web module dragged into the boot import closure.  Pure AST, always runs.
* compiled size -- ``mpy-cross`` output against per-module and per-group
  budgets.  Skipped when ``mpy-cross`` is absent.
* heap simulation -- the real ``.mpy`` artifacts imported under a MicroPython
  interpreter with a calibrated heap.  Skipped unless an interpreter is built
  (``tools/hostsim/build_micropython.sh``).

Run everything at once, including outside pytest, with ``python -m tools.hostsim``.
"""

import ast
import pathlib

import pytest

from tools.hostsim import budgets, runner, sizes
from tools.hostsim.graph import (
    ROOT,
    STATION_WEB_MODULES,
    boot_resident_modules,
    module_scope_imports,
)

SRC = pathlib.Path(ROOT) / "src"


# --------------------------------------------------------------------------
# Structural gates (no external tooling required)
# --------------------------------------------------------------------------


def _module_level_tables(path):
    """Module-scope collection literals, as ``(name, string_literal_count)``."""
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            elements = value.elts
        elif isinstance(value, ast.Dict):
            elements = list(value.values)
        else:
            continue
        strings = [
            e
            for e in elements
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        yield ast.unparse(node.targets[0]), len(strings)


@pytest.mark.parametrize(
    "path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_no_module_level_table_of_many_small_strings(path):
    """Each element of such a table is its own pinned GC object.

    ``font.py`` held 41 glyphs as tuples of seven ``"01010"`` strings: about
    400 objects and 24,544 bytes of heap, allocated at import and never freed.
    Packed into a single ``bytes`` blob the same pixels cost 1,632 bytes.  Use
    one packed string or ``bytes`` and slice on read instead.
    """
    offenders = [
        (name, count)
        for name, count in _module_level_tables(path)
        if count > budgets.MAX_STRING_LITERALS_PER_TABLE
    ]
    assert not offenders, (
        "%s has module-level string tables that pin one heap object per "
        "element: %s. Pack them into a single string/bytes literal and slice."
        % (path.relative_to(ROOT), offenders)
    )


def test_station_web_modules_stay_out_of_the_boot_import_closure():
    """The admin site must not load until a browser actually asks for it.

    These modules are imported inside functions on purpose.  Promoting one to
    module scope pins it from boot and takes the headroom the first request
    needs -- the shape of the original failure.
    """
    resident = set(boot_resident_modules())
    leaked = sorted(resident.intersection(STATION_WEB_MODULES))
    assert not leaked, (
        "station web modules reachable from main.py at module scope: %s. "
        "Import them inside the function that needs them." % leaked
    )


def test_heavy_provisioning_modules_are_not_imported_at_module_scope():
    """Session and KDF state stay absent until an authenticated request."""
    resident = set(boot_resident_modules())
    for module in ("src.provisioning.session", "src.provisioning.kdf_job"):
        assert module not in resident, "%s must stay lazily imported" % module


def test_web_server_does_not_import_machine_or_network():
    """The web surface is host-testable only while it owns no device imports."""
    for path in (SRC / "device" / "web").rglob("*.py"):
        source = path.read_text()
        for forbidden in ("import machine", "import network"):
            assert forbidden not in source, "%s imports %s" % (path, forbidden)


def test_boot_import_closure_is_derivable_and_non_trivial():
    """Guards the analysis itself; an empty closure would silence every gate."""
    resident = boot_resident_modules()
    assert len(resident) > 20
    assert "src.app" in resident and "src.config" in resident
    assert module_scope_imports(str(pathlib.Path(ROOT) / "main.py"))


# --------------------------------------------------------------------------
# Compiled-size gates
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def size_report():
    try:
        return sizes.report()
    except sizes.MpyCrossMissing as exc:
        pytest.skip(str(exc))


def test_compiled_sizes_are_within_budget(size_report):
    assert not size_report["breaches"], "\n".join(size_report["breaches"])


def test_boot_resident_compiled_size(size_report):
    assert size_report["boot_total"] <= budgets.BOOT_RESIDENT_MPY_BYTES


def test_station_web_compiled_size(size_report):
    assert size_report["web_total"] <= budgets.STATION_WEB_MPY_BYTES


# --------------------------------------------------------------------------
# Heap simulation gate
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def simulation():
    try:
        runner.find_micropython()
    except runner.SimulatorMissing as exc:
        pytest.skip(str(exc))
    return runner.run()


def test_every_module_imports_without_memory_error(simulation):
    """The exact failure from the field: importing the chain a request needs."""
    failures = simulation["boot_failure"] + simulation["web_failure"]
    assert not failures, "\n".join(failures)


def test_contiguous_allocation_survives_a_fully_resident_heap(simulation):
    """Free bytes are not enough; the first request needs a contiguous run."""
    failed = [
        size
        for size in budgets.SIM_REQUIRED_CONTIGUOUS
        if simulation.get("contiguous_%d" % size) != "ok"
    ]
    assert not failed, "no contiguous run available for sizes: %s" % failed


def test_simulated_heap_is_within_budget(simulation):
    problems = runner.breaches(simulation)
    assert not problems, "\n".join(problems)
