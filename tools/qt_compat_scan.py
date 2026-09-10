#!/usr/bin/env python3
"""Find (and optionally fix) code that breaks on QGIS 4 / Qt 6.

Every plugin in this repository ships as a single ZIP that must run unchanged on
QGIS 3.40+ (PyQt5 / Qt 5) and QGIS 4.x (PyQt6 / Qt 6). That is possible because
the *scoped* spellings are accepted by both bindings:

    Qt.AlignLeft            -> PyQt5 only      Qt.AlignmentFlag.AlignLeft   -> both
    dlg.exec_()             -> PyQt5 only      dlg.exec()                   -> both
    QgsField(n, QVariant.X) -> deprecated      QgsField(n, QMetaType.Type.X)-> both
    from PyQt5.QtGui import -> QGIS 3 only     from qgis.PyQt.QtGui import  -> both

This script reports each violation and, with --fix, rewrites the ones that can be
rewritten mechanically. Enum rewriting is driven by qt_enum_map.json.gz (see
gen_qt_enum_map.py) and uses the tokenizer, so text inside strings, comments and
docstrings is never touched.

    python tools/qt_compat_scan.py .            # report, exit 1 if anything found
    python tools/qt_compat_scan.py . --fix      # rewrite what can be rewritten
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ENUM_MAP = os.path.join(HERE, "qt_enum_map.json.gz")

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "tools"}

# A plugin that also runs outside QGIS cannot reach qgis.PyQt, so it needs a shim that
# names the bindings directly. Such a file opts out of the import rule by carrying this
# marker; everything else in it is still checked.
SHIM_MARKER = "qt-compat-shim"

# QVariant::Type is gone in Qt 6. QMetaType::Type is the replacement and the
# QgsField overload that takes it exists from QGIS 3.38, below our 3.40 floor.
QVARIANT_TO_QMETATYPE = {
    "Bool": "Bool",
    "ByteArray": "QByteArray",
    "Char": "QChar",
    "Date": "QDate",
    "DateTime": "QDateTime",
    "Double": "Double",
    "Int": "Int",
    "Invalid": "UnknownType",
    "List": "QVariantList",
    "LongLong": "LongLong",
    "Map": "QVariantMap",
    "String": "QString",
    "StringList": "QStringList",
    "Time": "QTime",
    "UInt": "UInt",
    "ULongLong": "ULongLong",
}

# Line-level patterns. (code, regex, replacement or None if not auto-fixable, message)
LINE_RULES = [
    (
        "PYQT-IMPORT",
        re.compile(r"\bfrom\s+PyQt[56](\.[A-Za-z_][A-Za-z0-9_]*)?\s+import\b"),
        lambda m: m.group(0).replace("PyQt5", "qgis.PyQt").replace("PyQt6", "qgis.PyQt"),
        "import Qt through qgis.PyQt so the same code runs on Qt5 and Qt6",
    ),
    (
        "PYQT-IMPORT",
        re.compile(r"\bimport\s+PyQt[56]\b"),
        None,
        "import Qt through qgis.PyQt so the same code runs on Qt5 and Qt6",
    ),
    (
        "EXEC-UNDERSCORE",
        re.compile(r"\.exec_\s*\("),
        lambda m: m.group(0).replace("exec_", "exec"),
        "exec_() was removed in PyQt6; exec() works on both",
    ),
    (
        "QREGEXP",
        re.compile(r"\bQRegExp\b"),
        None,
        "QRegExp was removed in Qt6; use QRegularExpression",
    ),
    (
        "QDESKTOPWIDGET",
        re.compile(r"\bQDesktopWidget\b|\.desktop\s*\(\s*\)"),
        None,
        "QDesktopWidget/QApplication.desktop() were removed in Qt6; use QScreen",
    ),
    (
        "SIP-SETAPI",
        re.compile(r"\bsip\.setapi\b"),
        None,
        "sip.setapi has no effect under PyQt6",
    ),
]

QVARIANT_RE = re.compile(r"\bQVariant\.([A-Za-z_][A-Za-z0-9_]*)\b")


class Finding:
    def __init__(self, path, line, code, message, fixed=False):
        self.path = path
        self.line = line
        self.code = code
        self.message = message
        self.fixed = fixed

    def __str__(self):
        mark = "fixed " if self.fixed else ""
        return f"{self.path}:{self.line}: {mark}[{self.code}] {self.message}"


def load_enum_map():
    with gzip.open(ENUM_MAP, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def iter_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def enum_edits(src, enum_map):
    """Locate unscoped enum access with the tokenizer.

    Returns [(row, col, member, enum_type, cls)] where (row, col) is the start of
    the member token, i.e. where "<EnumType>." must be inserted.
    """
    edits = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return edits

    names = [t for t in tokens if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT)]
    for i in range(len(names) - 2):
        cls_tok, dot_tok, member_tok = names[i], names[i + 1], names[i + 2]
        if cls_tok.type != tokenize.NAME or member_tok.type != tokenize.NAME:
            continue
        if dot_tok.type != tokenize.OP or dot_tok.string != ".":
            continue
        bucket = enum_map.get(cls_tok.string)
        if not bucket:
            continue
        enum_type = bucket.get(member_tok.string)
        if not enum_type:
            continue
        edits.append((member_tok.start[0], member_tok.start[1], member_tok.string, enum_type, cls_tok.string))
    return edits


def apply_enum_edits(src, edits):
    lines = src.splitlines(keepends=True)
    # right-to-left so earlier columns stay valid
    for row, col, member, enum_type, _cls in sorted(edits, reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:col] + enum_type + "." + line[col:]
    return "".join(lines)


def scan_file(path, enum_map, fix, root):
    rel = os.path.relpath(path, root).replace("\\", "/")
    # newline="" keeps CRLF/LF exactly as found, so a rewrite never churns line endings
    with open(path, encoding="utf-8", newline="") as fh:
        original = fh.read()
    src = original
    findings = []
    is_shim = SHIM_MARKER in original

    # 1. unscoped Qt enums (tokenizer-driven, so strings/comments are safe)
    edits = enum_edits(src, enum_map)
    for row, _col, member, enum_type, cls in edits:
        findings.append(
            Finding(rel, row, "UNSCOPED-ENUM", f"{cls}.{member} -> {cls}.{enum_type}.{member}", fix)
        )
    if edits and fix:
        src = apply_enum_edits(src, edits)

    # 2/3. line-level rewrites. Recomputed against the (possibly) edited source so
    #      reported line numbers stay meaningful.
    out_lines = []
    needs_qmetatype = False
    for lineno, line in enumerate(src.splitlines(keepends=True), 1):
        code_part = line.split("#", 1)[0]
        new_line = line

        for code, pattern, repl, message in LINE_RULES:
            if not pattern.search(code_part):
                continue
            if code == "PYQT-IMPORT" and is_shim:
                continue
            findings.append(Finding(rel, lineno, code, message, fix and repl is not None))
            if fix and repl is not None:
                new_line = pattern.sub(repl, new_line)

        for m in QVARIANT_RE.finditer(code_part):
            target = QVARIANT_TO_QMETATYPE.get(m.group(1))
            if target is None:
                continue
            findings.append(
                Finding(rel, lineno, "QVARIANT-TYPE", f"QVariant.{m.group(1)} -> QMetaType.Type.{target}", fix)
            )
            needs_qmetatype = True
            if fix:
                new_line = new_line.replace(f"QVariant.{m.group(1)}", f"QMetaType.Type.{target}")

        out_lines.append(new_line)

    src = "".join(out_lines)

    if needs_qmetatype and not re.search(r"\bimport\b.*\bQMetaType\b", src):
        findings.append(
            Finding(rel, 1, "QMETATYPE-IMPORT", "add QMetaType to the qgis.PyQt.QtCore import", False)
        )

    if fix and src != original:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(src)

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="directory to scan (default: .)")
    ap.add_argument("--fix", action="store_true", help="rewrite what can be rewritten mechanically")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    enum_map = load_enum_map()

    findings = []
    for path in iter_py_files(root):
        findings.extend(scan_file(path, enum_map, args.fix, root))

    if not findings:
        print("qt_compat_scan: clean — nothing to change for QGIS 4")
        return 0

    for f in sorted(findings, key=lambda f: (f.path, f.line, f.code)):
        print(f)

    unfixed = [f for f in findings if not f.fixed]
    print(f"\n{len(findings)} finding(s), {len(findings) - len(unfixed)} fixed, {len(unfixed)} need attention")
    return 1 if unfixed else 0


if __name__ == "__main__":
    sys.exit(main())
