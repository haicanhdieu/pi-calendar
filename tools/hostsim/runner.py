"""Drive the MicroPython heap simulation over the real deploy artifacts.

The simulation stages exactly what ``tools/deploy.py`` pushes -- the same
``.mpy`` files produced by the same ``mpy-cross`` -- then imports them under a
MicroPython interpreter whose heap is capped at the device's real size.  That
makes a ``MemoryError`` here mean the same thing it means on hardware, without
a deploy cycle.

Two fidelity limits are worth stating plainly:

* The host interpreter is a 64-bit build, so pointer-heavy structures cost
  about 1.25x what they cost on the 32-bit RP2040.  The simulation therefore
  fails earlier than the device, never later.
* There is no CYW43 driver, so Wi-Fi association and DHCP buffers are absent.

Build a matching interpreter with ``tools/hostsim/build_micropython.sh``; the
version must match the flashed firmware so the ``.mpy`` format is accepted.
"""

import importlib.util
import os
import shutil
import subprocess
import tempfile

from tools.hostsim import budgets
from tools.hostsim.graph import ROOT, boot_resident_modules, station_web_modules

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUILD = os.path.join(HERE, "build", "micropython")


class SimulatorMissing(Exception):
    """No MicroPython interpreter is available to run the simulation."""


def find_micropython():
    """Locate a MicroPython unix binary, or raise with build instructions."""
    candidates = [os.environ.get("MICROPYTHON"), DEFAULT_BUILD]
    candidates.append(shutil.which("micropython"))
    for candidate in candidates:
        if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise SimulatorMissing(
        "No MicroPython interpreter found. Build one matching the flashed "
        "firmware with `tools/hostsim/build_micropython.sh`, or set "
        "MICROPYTHON to an existing binary."
    )


def _load_deploy_module():
    """Import ``tools/deploy.py`` so staging cannot drift from deployment."""
    path = os.path.join(ROOT, "tools", "deploy.py")
    spec = importlib.util.spec_from_file_location("_pi_calendar_deploy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage(mpy_cross=None):
    """Stage the deploy tree plus stubs and probe; returns the directory."""
    deploy = _load_deploy_module()
    mpy_cross = mpy_cross or deploy.find_mpy_cross()
    staging = deploy.stage_tree(mpy_cross)

    for stub in ("machine.py", "network.py"):
        shutil.copy2(os.path.join(HERE, "stubs", stub), os.path.join(staging, stub))
    shutil.copy2(os.path.join(HERE, "probe.py"), os.path.join(staging, "probe.py"))

    boot = boot_resident_modules()
    web = station_web_modules()
    with open(os.path.join(staging, "_modules.py"), "w") as handle:
        handle.write("BOOT = %r\nWEB = %r\n" % (list(boot), list(web)))
    return staging


def parse(output):
    """Turn the probe's ``key=value`` lines into a dict (failures collected)."""
    result = {"boot_failure": [], "web_failure": []}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in ("boot_failure", "web_failure"):
            result[key].append(value)
        elif value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value
    return result


def run(heap_size=None, keep_staging=False):
    """Run the simulation and return the parsed probe results."""
    interpreter = find_micropython()
    heap_size = heap_size or budgets.SIM_HEAP_SIZE
    staging = stage()
    try:
        completed = subprocess.run(
            [interpreter, "-X", "heapsize=" + heap_size, "probe.py"],
            cwd=staging,
            capture_output=True,
            text=True,
        )
    finally:
        if keep_staging:
            print("Staged tree kept at:", staging)
        else:
            shutil.rmtree(staging, ignore_errors=True)

    result = parse(completed.stdout)
    result["returncode"] = completed.returncode
    result["stderr"] = completed.stderr
    result["interpreter"] = interpreter
    return result


def breaches(result):
    """Budget and correctness violations in a completed simulation run."""
    problems = []
    problems.extend("boot import failed -- " + f for f in result["boot_failure"])
    problems.extend("station web import failed -- " + f for f in result["web_failure"])

    boot_alloc = result.get("boot_alloc")
    if boot_alloc is not None and boot_alloc > budgets.SIM_BOOT_RESIDENT_BYTES:
        problems.append(
            "boot-resident heap %d exceeds budget %d (+%d)"
            % (
                boot_alloc,
                budgets.SIM_BOOT_RESIDENT_BYTES,
                boot_alloc - budgets.SIM_BOOT_RESIDENT_BYTES,
            )
        )

    boot_free = result.get("boot_free")
    if boot_free is not None and boot_free < budgets.SIM_MIN_FREE_AFTER_BOOT:
        problems.append(
            "free heap after boot %d is below the %d floor"
            % (boot_free, budgets.SIM_MIN_FREE_AFTER_BOOT)
        )

    for size in budgets.SIM_REQUIRED_CONTIGUOUS:
        outcome = result.get("contiguous_%d" % size)
        if outcome is not None and outcome != "ok":
            problems.append(
                "no contiguous %d-byte allocation once every module is resident"
                % size
            )

    if result.get("returncode") not in (0, None):
        problems.append("simulator exited %s: %s" % (result["returncode"], result["stderr"].strip()))
    return problems


def format_report(result):
    lines = [
        "interpreter        : %s" % result.get("interpreter", "?"),
        "heap total         : %s" % result.get("heap_total", "?"),
        "after boot imports : alloc=%s free=%s"
        % (result.get("boot_alloc", "?"), result.get("boot_free", "?")),
        "after web imports  : alloc=%s free=%s"
        % (result.get("web_alloc", "?"), result.get("web_free", "?")),
    ]
    contiguous = [
        "%s:%s" % (size, result.get("contiguous_%s" % size, "?"))
        for size in (512, 1024, 2048, 4096)
    ]
    lines.append("contiguous probe   : " + "  ".join(contiguous))
    return "\n".join(lines)
