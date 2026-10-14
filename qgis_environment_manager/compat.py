# -*- coding: utf-8 -*-
"""Which installed QGIS plugins declare support for QGIS 3 and QGIS 4 (no QGIS imports).

This reads each plugin's metadata.txt. It reports what a plugin *declares*: it cannot know whether the code
really runs on Qt 6. QGIS 4 only offers plugins that declare ``supportsQt6=True``, and when
``qgisMaximumVersion`` is missing QGIS assumes the last version of the minimum's major series
(minimum 3.0 -> maximum 3.99).
"""
from __future__ import annotations

import configparser
import os
import re

OK, CHECK, NO = "ok", "check", "no"


def parse_metadata(text: str) -> dict:
    cp = configparser.RawConfigParser(strict=False)
    cp.optionxform = str  # keys are camelCase
    cp.read_string(text)
    return dict(cp["general"]) if cp.has_section("general") else {}


def parse_version(value, default=None):
    """'3.44.5' -> (3, 44); '' or junk -> default."""
    nums = re.findall(r"\d+", str(value or ""))
    if not nums:
        return default
    return (int(nums[0]), int(nums[1]) if len(nums) > 1 else 0)


def is_true(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes")


def scan(dirs) -> list:
    """One row per plugin folder (with a metadata.txt) found in ``dirs``, sorted by name."""
    rows, seen = [], set()
    for base in dirs:
        if not base or not os.path.isdir(base):
            continue
        for folder in sorted(os.listdir(base)):
            path = os.path.join(base, folder)
            meta_path = os.path.join(path, "metadata.txt")
            if folder in seen or not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path, encoding="utf-8", errors="replace") as fh:
                    meta = parse_metadata(fh.read())
            except (OSError, configparser.Error):
                meta = {}
            seen.add(folder)
            rows.append({
                "id": folder, "path": path,
                "name": (meta.get("name") or folder).strip(),
                "version": (meta.get("version") or "").strip(),
                "min": (meta.get("qgisMinimumVersion") or "").strip(),
                "max": (meta.get("qgisMaximumVersion") or "").strip(),
                "qt6": is_true(meta.get("supportsQt6", "")),
                "broken": not meta,
            })
    return sorted(rows, key=lambda r: r["name"].lower())


def effective_range(row):
    """((min_major, min_minor), (max_major, max_minor)) as QGIS reads the metadata."""
    lo = parse_version(row["min"], (0, 0))
    hi = parse_version(row["max"], (lo[0], 99))
    return lo, hi


def assess(row, qgis_major: int) -> dict:
    """{'status': ok|check|no, 'reason': key} for running on QGIS ``qgis_major``."""
    if row.get("broken"):
        return {"status": CHECK, "reason": "unreadable"}
    lo, hi = effective_range(row)
    if hi[0] < qgis_major:
        return {"status": NO, "reason": "max_below"}
    if lo[0] > qgis_major:
        return {"status": NO, "reason": "min_above"}
    if qgis_major >= 4 and not row["qt6"]:
        return {"status": CHECK, "reason": "no_qt6"}
    return {"status": OK, "reason": "declared"}


def summarize(rows, qgis_major: int) -> dict:
    out = {OK: 0, CHECK: 0, NO: 0}
    for r in rows:
        out[assess(r, qgis_major)["status"]] += 1
    return out
