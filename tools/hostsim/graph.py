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

# Reaching the station admin site imports these on top of the resident set.
# `coordinator` is included because a station-mode tick pulls it in and then
# keeps it, even though `main.py` only names it lazily.
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


def boot_resident_modules(entry="main.py"):
    """Modules pinned on the heap from boot, as a sorted tuple."""
    resident = set()
    pending = [os.path.join(ROOT, entry)]
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


def station_web_modules():
    """Modules added on top of the resident set to serve the admin site."""
    resident = set(boot_resident_modules())
    return tuple(m for m in STATION_WEB_MODULES if m not in resident)
