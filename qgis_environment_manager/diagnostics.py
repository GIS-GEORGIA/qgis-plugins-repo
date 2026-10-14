# -*- coding: utf-8 -*-
"""Facts about this QGIS and what they mean. ``analyze`` and ``report_text`` are pure; ``gather_facts`` asks QGIS."""
from __future__ import annotations

import datetime
import platform
import sys

from . import compat, strings
from .qgis_installer import requirements, system

KEY_EXPIRES = datetime.date(2027, 8, 8)       # the QGIS repository signing key (see qgis_installer.system.KEY_FPR)
KEY_WARN_DAYS = 60


def gather_facts() -> dict:
    """Everything we can read from the running QGIS (call from the GUI thread)."""
    from qgis.core import Qgis, QgsApplication
    from qgis.PyQt.QtCore import qVersion

    facts = {
        "qgis_version": Qgis.version().split("-")[0],
        "qgis_release": Qgis.version().partition("-")[2],
        "python": sys.version.split()[0],
        "qt": qVersion(),
        "os": platform.platform(),
        "is_linux": sys.platform.startswith("linux"),
        "runtime": requirements.qgis_runtime(),
        "prefix": QgsApplication.prefixPath(),
        "profile": QgsApplication.qgisSettingsDirPath(),
        "gdal": "",
    }
    try:
        from osgeo import gdal
        facts["gdal"] = gdal.VersionInfo("RELEASE_NAME")
    except Exception:  # noqa: BLE001 - optional
        pass
    return facts


def _major_minor(version: str):
    return compat.parse_version(version, (0, 0))


def analyze(facts: dict, installs=None, today=None) -> list:
    """[(level, key, params)] with level info|warn: findings to show, in order."""
    today = today or datetime.date.today()
    cur = _major_minor(facts["qgis_version"])
    ltr = _major_minor(system.LTR)
    latest = _major_minor(system.LATEST)
    out = []
    if cur == ltr:
        out.append(("info", "fi_ltr", {"v": "{}.{}".format(*ltr)}))
    elif cur == latest:
        out.append(("info", "fi_latest", {"v": "{}.{}".format(*latest)}))
    elif cur < ltr:
        out.append(("warn", "fi_older", {"v": facts["qgis_version"], "ltr": "{}.{}".format(*ltr)}))
    if cur[0] < latest[0]:
        out.append(("info", "fi_has4", {"latest": "{}.{}".format(*latest)}))
    if facts.get("runtime") == "flatpak":
        out.append(("warn", "fi_flatpak", {}))
    elif facts.get("runtime") == "snap":
        out.append(("warn", "fi_snap", {}))
    if installs and any(it.get("kind") == "repo" for it in installs):
        left = (KEY_EXPIRES - today).days
        if left < 0:
            out.append(("warn", "fi_key_expired", {"date": KEY_EXPIRES.isoformat()}))
        elif left <= KEY_WARN_DAYS:
            out.append(("warn", "fi_key_soon", {"date": KEY_EXPIRES.isoformat()}))
    return out


def fact_rows(facts: dict, lang: str):
    t = lambda k, **kw: strings.t(k, lang, **kw)  # noqa: E731
    version = facts["qgis_version"] + (" ({})".format(facts["qgis_release"]) if facts.get("qgis_release") else "")
    rows = [
        (t("f_version"), version),
        (t("f_python"), facts["python"]),
        (t("f_qt"), facts["qt"]),
    ]
    if facts.get("gdal"):
        rows.append((t("f_gdal"), facts["gdal"]))
    rows += [
        (t("f_os"), facts["os"]),
        (t("f_runtime"), t("rt_" + facts["runtime"])),
        (t("f_prefix"), facts["prefix"]),
        (t("f_profile"), facts["profile"]),
    ]
    return rows


def report_text(facts: dict, findings, installs, lang: str, labels=None) -> str:
    """Plain-text report for support requests (what the Copy button puts on the clipboard)."""
    t = lambda k, **kw: strings.t(k, lang, **kw)  # noqa: E731
    lines = ["QGIS Environment Manager", ""]
    lines += ["{}: {}".format(k, v) for k, v in fact_rows(facts, lang)]
    lines += ["", t("h_findings") + ":"]
    lines += ["- " + t(key, **params) for _lvl, key, params in findings] or ["- " + t("fi_none")]
    if installs:
        lines += ["", t("h_installs") + ":"] + ["- " + (labels(it) if labels else str(it)) for it in installs]
    return "\n".join(lines)
