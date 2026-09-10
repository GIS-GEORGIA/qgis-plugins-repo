#!/usr/bin/env python3
"""Regenerate tools/qt_enum_map.json.gz.

Run this with a **PyQt6** interpreter (e.g. QGIS 4's python-qgis.bat). It walks every
Qt class and records, for each enum member, which enum type it belongs to:

    {"Qt": {"AlignLeft": "AlignmentFlag", ...}, "QMessageBox": {"Yes": "StandardButton", ...}}

qt_compat_scan.py uses that to rewrite PyQt5-style unscoped enum access
(``Qt.AlignLeft``) into the scoped form (``Qt.AlignmentFlag.AlignLeft``) that both
PyQt5 and PyQt6 accept.

Only needs re-running when targeting a newer Qt release.

    "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" tools/gen_qt_enum_map.py
"""

import enum
import gzip
import json
import os
import sys

MODULES = (
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtXml",
    "QtSvg",
    "QtPrintSupport",
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qt_enum_map.json.gz")


def load_modules():
    mods = {}
    for name in MODULES:
        for pkg in ("qgis.PyQt", "PyQt6"):
            try:
                mods[name] = __import__(f"{pkg}.{name}", fromlist=["*"])
                break
            except ImportError:
                continue
        else:
            print(f"  skipped {name} (not available)", file=sys.stderr)
    return mods


def build(mods):
    """class name -> {member name: enum type name}, dropping ambiguous members."""
    out = {}
    ambiguous = {}
    for mod in mods.values():
        for cls_name in dir(mod):
            cls = getattr(mod, cls_name)
            if not isinstance(cls, type):
                continue
            for enum_name in dir(cls):
                try:
                    enum_type = getattr(cls, enum_name)
                except Exception:
                    continue
                if not isinstance(enum_type, type):
                    continue
                try:
                    if not issubclass(enum_type, enum.Enum):
                        continue
                except Exception:
                    continue
                members = getattr(enum_type, "__members__", None)
                if not members:
                    continue
                bucket = out.setdefault(cls_name, {})
                for member in members:
                    if bucket.get(member, enum_name) != enum_name:
                        ambiguous.setdefault(cls_name, set()).add(member)
                    bucket[member] = enum_name

    for cls_name, members in ambiguous.items():
        for member in members:
            out[cls_name].pop(member, None)
    return out, ambiguous


def main():
    if sys.version_info < (3, 8):
        sys.exit("needs Python 3.8+")
    mods = load_modules()
    if "QtCore" not in mods:
        sys.exit("no Qt bindings found — run this under a PyQt6 interpreter")

    table, ambiguous = build(mods)
    payload = json.dumps(table, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with gzip.GzipFile(OUT, "wb", mtime=0) as fh:
        fh.write(payload)

    total = sum(len(v) for v in table.values())
    dropped = sum(len(v) for v in ambiguous.values())
    print(f"{OUT}: {len(table)} classes, {total} members ({dropped} ambiguous dropped)")


if __name__ == "__main__":
    main()
