"""What the installed QGIS plugins import that this Python does not have. Reads only, no UI.

The commonest QGIS plugin failure is "No module named 'openpyxl'" when the plugin loads. ``scan_plugin`` reads a plugin's ``.py`` files
(never runs them) and lists the third-party modules they import; ``missing`` says which of those this Python cannot import; ``packages``
maps what is missing to the system package of every component the program knows (the same table as ``components``), and says which
modules it has no package for.

What counts as third-party: not the standard library, not what QGIS itself provides (qgis, PyQt, processing, ...), and not a module that is
part of the plugin (a ``.py`` file or a package anywhere in its folder, so ``from i18n import t`` or ``import core.x`` are the plugin's own).
Imports at the top of a module that are not guarded are *required* (the plugin does not load without them); imports inside a function or
inside ``try: ... except ImportError`` are *optional* (the plugin works without, with less).
"""
import ast
import importlib.util
import os
import sys

from . import i18n, requirements

QGIS_PROVIDED = frozenset({"qgis", "PyQt5", "PyQt6", "sip", "processing", "pyplugin_installer", "plugins", "qgis_tests"})
SKIP_DIRS = frozenset({"__pycache__", "tests", "test", "docs", "doc", "examples", "extlibs", ".git"})
MAX_BYTES = 2 * 1024 * 1024                    # a source file larger than this is not read

# top-level module name -> the component (requirements.REQ id) that provides it
MODULE_TO_COMPONENT = {"osgeo": "gdal-python", "numpy": "numpy", "pandas": "pandas", "scipy": "scipy", "matplotlib": "matplotlib",
                       "shapely": "shapely", "pyproj": "pyproj", "rasterio": "rasterio", "fiona": "fiona", "psycopg2": "psycopg2",
                       "geopandas": "geopandas", "openpyxl": "openpyxl", "requests": "requests", "yaml": "pyyaml", "lxml": "lxml",
                       "PIL": "pillow", "jinja2": "jinja2", "sqlalchemy": "sqlalchemy"}


def stdlib_names():
    return set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}


def _local_names(root):
    """Module names that belong to the plugin itself: every .py file and package folder anywhere inside it."""
    names = {os.path.basename(os.path.normpath(root))}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for d in dirs:
            names.add(d)
        for f in files:
            if f.endswith(".py"):
                names.add(f[:-3])
    return names


def _guard_types(handler):
    t = handler.type
    if t is None:
        return {"*"}
    nodes = t.elts if isinstance(t, ast.Tuple) else [t]
    return {n.id for n in nodes if isinstance(n, ast.Name)}


def _is_type_checking(test):
    """``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:``: its body never runs, so its imports are not needed."""
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")


def _is_import_guard(node):
    """try: import x / except ImportError (ModuleNotFoundError, Exception, bare): the import is optional."""
    for h in node.handlers:
        if _guard_types(h) & {"ImportError", "ModuleNotFoundError", "Exception", "*", "BaseException"}:
            return True
    return False


def _imports(tree):
    """[(top-level module, optional?)] for every absolute import in the tree."""
    found = []

    def visit(node, optional):
        for child in ast.iter_child_nodes(node):
            opt = optional
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                opt = True
            if isinstance(child, ast.If) and _is_type_checking(child.test):
                for stmt in child.orelse:
                    visit_stmt(stmt, optional)
                continue
            if isinstance(child, ast.Try) and _is_import_guard(child):
                for stmt in child.body:
                    visit_stmt(stmt, True)
                for part in (child.handlers, child.orelse, child.finalbody):
                    for stmt in part:
                        visit_stmt(stmt, optional)
                continue
            visit_stmt(child, opt)

    def visit_stmt(node, optional):
        if isinstance(node, ast.Import):
            found.extend((a.name.split(".")[0], optional) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.append((node.module.split(".")[0], optional))
        else:
            visit(node, optional)

    visit(tree, False)
    return found


def scan_plugin(path):
    """{'required': {modules}, 'optional': {modules}, 'unreadable': [files]} for one plugin folder."""
    if not os.path.isdir(path):
        raise FileNotFoundError("not a plugin folder: " + path)       # never "needs nothing" for a place that is not there
    local = _local_names(path)
    skip = stdlib_names() | QGIS_PROVIDED | local
    required, optional, bad = set(), set(), []
    for dirpath, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            full = os.path.join(dirpath, f)
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    bad.append(os.path.relpath(full, path))
                    continue
                with open(full, encoding="utf-8", errors="replace") as fh:
                    tree = ast.parse(fh.read(), filename=full)
            except (OSError, SyntaxError, ValueError):
                bad.append(os.path.relpath(full, path))
                continue
            for mod, opt in _imports(tree):
                if mod in skip:
                    continue
                (optional if opt else required).add(mod)
    optional -= required
    return {"required": required, "optional": optional, "unreadable": sorted(bad)}


def can_import(module, find_spec=None):
    find_spec = find_spec or importlib.util.find_spec
    try:
        return find_spec(module) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def missing(scan, find_spec=None):
    return {"required": sorted(m for m in scan["required"] if not can_import(m, find_spec)),
            "optional": sorted(m for m in scan["optional"] if not can_import(m, find_spec))}


def packages(modules, pm, pyver=None):
    """-> ({component id: [package names]}, [modules with no component or no package for this package manager])."""
    comp, manual = {}, []
    for m in modules:
        rid = MODULE_TO_COMPONENT.get(m)
        names = requirements.packages_for([rid], pm, pyver)[0] if rid and rid in requirements.REQ else []
        if names:
            comp[rid] = names
        else:
            manual.append(m)
    return comp, manual


def plugin_dirs(roots):
    """Folders of installed plugins under the given plugin roots (a folder with a metadata.txt)."""
    out = []
    for root in roots:
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for n in names:
            p = os.path.join(root, n)
            if os.path.isfile(os.path.join(p, "metadata.txt")):
                out.append(p)
    return out


def report(roots, pm, find_spec=None, pyver=None):
    """[{plugin, path, required_missing, optional_missing, components, manual, unreadable}] for every plugin that lacks something
    (plugins with nothing missing are left out; ``checked`` counts all of them)."""
    importlib.invalidate_caches()                  # something may have been installed since this process started
    rows, checked = [], 0
    for path in plugin_dirs(roots):
        checked += 1
        scan = scan_plugin(path)
        miss = missing(scan, find_spec)
        if not (miss["required"] or miss["optional"] or scan["unreadable"]):
            continue
        comp, manual = packages(miss["required"] + miss["optional"], pm, pyver)
        rows.append({"plugin": os.path.basename(path), "path": path, "required_missing": miss["required"], "optional_missing": miss["optional"],
                     "components": comp, "manual": manual, "unreadable": scan["unreadable"]})
    return {"rows": rows, "checked": checked}


def wanted_components(result, optional=False):
    """The component ids that would close the gaps that have a package: the required ones, and the optional ones when asked for."""
    wanted = []
    for r in result["rows"]:
        for m in r["required_missing"] + (r["optional_missing"] if optional else []):
            rid = MODULE_TO_COMPONENT.get(m)
            if rid and rid in r["components"] and rid not in wanted:
                wanted.append(rid)
    return wanted


def lines(result, lang="en"):
    """A report as lines of text: who needs what, how to get it, what has no package."""
    t = lambda k, **kw: i18n.t(k, lang, **kw)  # noqa: E731
    out = [t("pd_head", n=result["checked"])]
    if not result["rows"]:
        out.append(t("pd_none"))
    for r in result["rows"]:
        for key, mods in (("pd_required", r["required_missing"]), ("pd_optional", r["optional_missing"])):
            if not mods:
                continue
            out.append(t(key, plugin=r["plugin"], mods=", ".join(mods)))
            comp = {c: p for c, p in r["components"].items() if any(MODULE_TO_COMPONENT.get(m) == c for m in mods)}
            if comp:
                out.append(t("pd_install", pkgs=" ".join(sorted({n for names in comp.values() for n in names}))))
            manual = [m for m in mods if m in r["manual"]]
            if manual:
                out.append(t("pd_manual", mods=", ".join(manual)))
        if r["unreadable"]:
            out.append(t("pd_unreadable", files=", ".join(r["unreadable"][:5])))
    return out
