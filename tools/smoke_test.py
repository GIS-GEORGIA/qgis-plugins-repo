#!/usr/bin/env python3
"""Load every built plugin ZIP inside a real QGIS Python and report what breaks.

This is the check that actually proves the QGIS 3 / QGIS 4 claim: it installs each
plugin exactly as a user would (from plugins/*.zip), imports every module in it, and
calls classFactory() with a stub iface — the same entry point QGIS uses. Anything
that only exists in Qt5 (unscoped enums, exec_(), PyQt5 imports) blows up here.

Run it once per QGIS you support:

    "C:\\Program Files\\QGIS 3.44.5\\bin\\python-qgis.bat" tools/smoke_test.py
    "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat"  tools/smoke_test.py

Exit code is non-zero if any plugin fails to load.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pkgutil
import sys
import tempfile
import traceback
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "tools", "plugins.json")

# Subpackages that are shipped for reference but are not part of the load path.
SKIP_SUBMODULES = ("tests",)


def brief_error() -> str:
    """One line: the exception, plus the deepest frame that lives in the plugin."""
    exc_type, exc, tb = sys.exc_info()
    frames = traceback.extract_tb(tb)
    where = ""
    for frame in reversed(frames):
        if os.path.basename(frame.filename) != os.path.basename(__file__):
            where = f" (at {os.path.basename(frame.filename)}:{frame.lineno})"
            break
    return traceback.format_exception_only(exc_type, exc)[-1].strip() + where


class StubIface:
    """Permissive stand-in for QgisInterface: any attribute access returns a callable."""

    def __getattr__(self, name):
        return StubIface()

    def __call__(self, *args, **kwargs):
        return StubIface()

    def __bool__(self):
        return True


def qgis_version() -> str:
    from qgis.core import Qgis

    return Qgis.QGIS_VERSION


def qt_version() -> str:
    from qgis.PyQt.QtCore import QT_VERSION_STR

    return QT_VERSION_STR


def submodule_names(package) -> list[str]:
    names = []
    for _finder, name, _ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        tail = name[len(package.__name__) + 1 :]
        if tail.split(".")[0] in SKIP_SUBMODULES:
            continue
        names.append(name)
    return sorted(names)


def check_plugin(plugin: dict, workdir: str) -> list[str]:
    """Extract, import and instantiate one plugin. Returns a list of error strings."""
    errors: list[str] = []
    zip_path = os.path.join(ROOT, "plugins", plugin["zip"])
    target = os.path.join(workdir, plugin["id"])
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)

    folder = plugin["folder"]
    sys.path.insert(0, target)
    try:
        try:
            package = importlib.import_module(folder)
        except Exception:
            return [f"import {folder}: {brief_error()}"]

        factory = getattr(package, "classFactory", None)
        if factory is None:
            errors.append(f"{folder}: no classFactory()")
        else:
            try:
                factory(StubIface())
            except Exception:
                errors.append(f"{folder}.classFactory(): {brief_error()}")

        for name in submodule_names(package):
            try:
                importlib.import_module(name)
            except Exception:
                errors.append(f"import {name}: {brief_error()}")
    finally:
        sys.path.remove(target)
        for name in list(sys.modules):
            if name == folder or name.startswith(folder + "."):
                del sys.modules[name]
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="check just this plugin id")
    args = ap.parse_args()

    from qgis.core import QgsApplication

    app = QgsApplication([], False)
    QgsApplication.initQgis()

    print(f"QGIS {qgis_version()}   Qt {qt_version()}   Python {sys.version.split()[0]}")
    print("-" * 72)

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    failures = 0
    with tempfile.TemporaryDirectory(prefix="qgis-plugin-smoke-") as workdir:
        for plugin in manifest["plugins"]:
            if args.only and plugin["id"] != args.only:
                continue
            errors = check_plugin(plugin, workdir)
            status = "ok" if not errors else "FAIL"
            print(f"{status:>4}  {plugin['id']}")
            for err in errors:
                failures += 1
                for line in err.splitlines():
                    print(f"        {line}")

    QgsApplication.exitQgis()
    del app

    print("-" * 72)
    print("all plugins loaded" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
