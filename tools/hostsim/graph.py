"""Static import-graph analysis of what the Pico keeps resident.

The heap cost that matters is not a file's size on flash but which modules are
*live at once*.  MicroPython copies a ``.mpy``'s bytecode and builds every
function, constant table and module dict on the heap at import, and a module
is never collected, so the module-level import closure from ``main.py`` is
exactly the set that is pinned for the device's whole uptime.

Imports written inside a function body are deliberately lazy and are excluded:
that is how the station web surface stays absent until a browser arrives.
Moving one of those to module scope silently enlarges the resident set, which
is the regression these helpers exist to catch.
"""

import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Entry points whose module-scope imports define what each boot mode pins.
# `main.py` holds only what both modes need; the clock stack and the config
# stack each live behind their own entry module so neither pays for the other.
CLOCK_MODE_ENTRY = os.path.join("src", "device", "clock_mode.py")
CONFIG_MODE_ENTRY = os.path.join("src", "device", "config_mode.py")

# Reaching the station admin site imports these on top of the resident set.
# `coordinator` is included because a station-mode tick pulls it in and then
# keeps it, even though the entry modules only name it lazily.
#
# The second group is the authenticated *request* path: lazily imported inside
# route handlers, resident from the first request that touches them, and the
# cause of issue #2.  Leaving them out modelled a device that does not exist --
# a browser reaching /settings/add imports them and never gives them back.
STATION_WEB_MODULES = (
    "src.device.network.coordinator",
    "src.device.web.http_parse",
    "src.device.web.server",
    "src.device.web.pages",
    "src.device.web.page_login_content",
    "src.device.web.page_settings_content",
    "src.device.web.router",
    "src.provisioning.verifier",
    "src.provisioning.session",
    # Authenticated request path (issue #2).
    "src.provisioning.kdf_job",
    "src.device.web.settings_post",
    "src.device.web.alert_route",
    "src.device.web.alert_validation",
    "src.device.web.page_alert_editor",
    "src.device.web.postpone_route",
)


def module_path(module):
    """Source path for a dotted ``src.*`` module, or None when it has none."""
    base = os.path.join(ROOT, module.replace(".", os.sep))
    for candidate in (base + ".py", os.path.join(base, "__init__.py")):
        if os.path.exists(candidate):
            return candidate
    return None


class _ModuleScopeImports(ast.NodeVisitor):
    """Collect ``src.*`` imports that execute at module scope."""

    def __init__(self):
        self.found = set()

    # Function bodies run later (or never); their imports are not resident.
    def visit_FunctionDef(self, node):
        pass

    def visit_AsyncFunctionDef(self, node):
        pass

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name.startswith("src"):
                self.found.add(alias.name)

    def visit_ImportFrom(self, node):
        if node.level or not node.module or not node.module.startswith("src"):
            return
        for alias in node.names:
            # ``from src.device.web import pages`` names a module; ``from
            # src.config import SCREEN_WIDTH`` names an attribute of one.
            submodule = node.module + "." + alias.name
            if module_path(submodule) is not None:
                self.found.add(submodule)
            else:
                self.found.add(node.module)


def module_scope_imports(path):
    with open(path) as handle:
        tree = ast.parse(handle.read())
    visitor = _ModuleScopeImports()
    visitor.visit(tree)
    return visitor.found


def _closure(entries):
    """Modules pinned on the heap once every entry module is imported."""
    resident = set()
    pending = [os.path.join(ROOT, entry) for entry in entries]
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        for module in module_scope_imports(path):
            if module in resident:
                continue
            resident.add(module)
            child = module_path(module)
            if child is not None:
                pending.append(child)
    return tuple(sorted(resident))


def boot_resident_modules(entry=None):
    """Modules pinned from a normal (clock) boot, as a sorted tuple.

    ``entry`` overrides the default pair for callers that want one module's
    closure in isolation; the default is the real clock-mode boot.
    """
    if entry is not None:
        return _closure((entry,))
    return _closure(("main.py", CLOCK_MODE_ENTRY))


def config_resident_modules():
    """Modules pinned from a config-mode boot, as a sorted tuple.

    Config mode never constructs App, the clock/calendar/settings views, the
    compositor or the touch stack, so none of them are resident while the
    station web surface is live.  That separation is the entire point: the two
    sets no longer have to fit in the same 179,328-byte heap at once.
    """
    return _closure(("main.py", CONFIG_MODE_ENTRY))


def station_web_modules(resident=None):
    """Modules added on top of a resident set to serve the admin site."""
    if resident is None:
        resident = config_resident_modules()
    resident = set(resident)
    return tuple(m for m in STATION_WEB_MODULES if m not in resident)
