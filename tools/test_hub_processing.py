#!/usr/bin/env python3
"""The Hub's Processing algorithms, run in a QGIS Python (no window, throw-away profile):

    "C:\\Program Files\\QGIS 3.44.5\\bin\\python-qgis.bat" tools/test_hub_processing.py
    "C:\\Program Files\\QGIS 4.2.2\\bin\\python-qgis.bat"  tools/test_hub_processing.py

An offline "server" (this repo's catalog.json, its signature and zips) is injected through
``processing_algorithms.FETCH``. The profile is a temporary folder: the script aborts if it
cannot prove that, so it can never touch your real QGIS profile.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP = tempfile.mkdtemp(prefix="gg_hubproc_")
os.environ["QGIS_CUSTOM_CONFIG_PATH"] = os.path.join(TMP, "profile")

from qgis.core import Qgis, QgsApplication  # noqa: E402

app = QgsApplication([], False)
app.initQgis()
if os.path.normcase(TMP) not in os.path.normcase(QgsApplication.qgisSettingsDirPath()):
    print("REFUSING TO RUN: the QGIS profile is not the temporary one:", QgsApplication.qgisSettingsDirPath())
    sys.exit(2)

sys.path.append(os.path.join(QgsApplication.pkgDataPath(), "python", "plugins"))
import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

from gis_georgia_hub import installer_core, processing_algorithms as pa  # noqa: E402
from gis_georgia_hub.processing_provider import HubProvider  # noqa: E402

PROVIDER = HubProvider()
assert QgsApplication.processingRegistry().addProvider(PROVIDER)

FAILS = []
CALLS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (" " + str(extra) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def section(title):
    print("\n== " + title)


def serve(url):
    CALLS.append(url)
    installer_core.check_url(url)
    clean = url.split("?")[0].split("://", 1)[1].split("/", 1)[1]
    with open(os.path.join(ROOT, *clean.split("/")), "rb") as fh:
        return fh.read()


pa.FETCH = serve


def run(alg, params, expect_error=False):
    try:
        res = processing.run("gis_georgia_hub:" + alg, params)
    except Exception as exc:  # noqa: BLE001
        if expect_error:
            return exc
        raise
    if expect_error:
        raise AssertionError("expected a failure of " + alg)
    return res


def test_registration():
    section("provider")
    ids = {a.id() for a in PROVIDER.algorithms()}
    for want in ("install_plugin", "update_plugins", "list_catalog"):
        check("registered " + want, "gis_georgia_hub:" + want in ids, sorted(ids))


def test_list():
    section("list_catalog")
    res = run("list_catalog", {"REFRESH": True, "OUTPUT": "memory:"})
    rows = {f["id"]: f for f in res["OUTPUT"].getFeatures()}
    check("every catalog plugin is listed", len(rows) >= 15 and "calculate_geometry" in rows, len(rows))
    check("states: not installed, Hub is 'self'",
          rows["calculate_geometry"]["state"] == "not_installed" and rows["gis_georgia_hub"]["state"] == "self",
          (rows["calculate_geometry"]["state"], rows["gis_georgia_hub"]["state"]))
    check("algorithm counts come through", rows["owners_analyzer"]["algorithms"] == 3, rows["owners_analyzer"]["algorithms"])
    check("catalog and signature were fetched", any(u.endswith("catalog.json.sig") for u in CALLS), CALLS[:3])
    CALLS.clear()
    run("list_catalog", {"REFRESH": False, "OUTPUT": "memory:"})
    check("REFRESH off uses the verified saved copy (no network)", CALLS == [], CALLS)


def test_install():
    section("install_plugin")
    pid = "calculate_geometry"
    res = run("install_plugin", {"PLUGIN": pid, "ACTION": 0})
    ver = installer_core.installed_version(pid)
    check("installed into the temporary profile", ver and ver == res["VERSION"] and res["CHANGED"] is True, res)
    check("headless: files in place, not started", res["STARTED"] is False)
    res = run("install_plugin", {"PLUGIN": pid, "ACTION": 0, "REFRESH": False})
    check("second run is a no-op", res["CHANGED"] is False and res["VERSION"] == ver, res)

    res = run("install_plugin", {"PLUGIN": "Calculate-Geometry", "ACTION": 0, "REFRESH": False})
    check("the catalog id spelling works too", res["CHANGED"] is False)

    e = run("install_plugin", {"PLUGIN": "no_such_plugin", "ACTION": 0}, expect_error=True)
    check("unknown plugin is rejected", "not a GIS GEORGIA plugin" in str(e), e)
    e = run("install_plugin", {"PLUGIN": "gis_georgia_hub", "ACTION": 0}, expect_error=True)
    check("the Hub does not change itself", "does not change itself" in str(e), e)
    e = run("install_plugin", {"PLUGIN": "../../etc", "ACTION": 0}, expect_error=True)
    check("path-like input is just an unknown id", "not a GIS GEORGIA plugin" in str(e), e)

    res = run("install_plugin", {"PLUGIN": pid, "ACTION": 1, "REFRESH": False})
    check("uninstall removes it", res["CHANGED"] is True and installer_core.installed_version(pid) is None)
    res = run("install_plugin", {"PLUGIN": pid, "ACTION": 1, "REFRESH": False})
    check("uninstalling twice is harmless", res["CHANGED"] is False)


def test_update_plugins():
    section("update_plugins")
    for pid in ("owners_analyzer", "transliterator"):
        run("install_plugin", {"PLUGIN": pid, "ACTION": 0, "REFRESH": False})
        meta = os.path.join(installer_core.plugins_dir(), pid, "metadata.txt")
        with open(meta, encoding="utf-8") as fh:
            txt = fh.read()
        with open(meta, "w", encoding="utf-8") as fh:
            fh.write(txt.replace("version=", "version=0.0.", 1))
    res = run("update_plugins", {"REFRESH": False, "DRY_RUN": True})
    check("dry run lists both and changes nothing",
          res["UPDATED"] == 2 and "owners_analyzer" in res["NAMES"] and "transliterator" in res["NAMES"]
          and installer_core.installed_version("transliterator").startswith("0.0."), res)
    res = run("update_plugins", {"REFRESH": False, "DRY_RUN": False})
    check("update brings both to the catalog versions", res["UPDATED"] == 2
          and not installer_core.installed_version("transliterator").startswith("0.0."), res)
    res = run("update_plugins", {"REFRESH": False, "DRY_RUN": False})
    check("nothing left to update", res["UPDATED"] == 0, res)
    for pid in ("owners_analyzer", "transliterator"):
        installer_core.uninstall(pid)


def test_untrusted_catalog():
    section("untrusted catalogs are refused")
    good = pa.FETCH

    def altered(url):
        data = serve(url)
        return data.replace(b"GIS", b"gis", 1) if url.endswith("catalog.json") else data

    pa.FETCH = altered
    e = run("list_catalog", {"REFRESH": True, "OUTPUT": "memory:"}, expect_error=True)
    check("altered catalog: rejected with the reason", "Catalog rejected" in str(e) and "does not match" in str(e), e)

    def unsigned(url):
        if url.endswith(".sig"):
            raise installer_core.InstallError("404")
        return serve(url)

    pa.FETCH = unsigned
    e = run("install_plugin", {"PLUGIN": "calculate_geometry", "ACTION": 0}, expect_error=True)
    check("unsigned catalog: nothing installed", installer_core.installed_version("calculate_geometry") is None
          and "Could not load the catalog" in str(e), e)

    def bad_zip(url):
        data = serve(url)
        return data + b"x" if url.split("?")[0].endswith("calculate_geometry.zip") else data

    pa.FETCH = bad_zip
    e = run("install_plugin", {"PLUGIN": "calculate_geometry", "ACTION": 0}, expect_error=True)
    check("a changed zip fails its checksum, nothing installed",
          "Checksum mismatch" in str(e) and installer_core.installed_version("calculate_geometry") is None, e)
    pa.FETCH = good


print("QGIS", Qgis.version(), "| profile", QgsApplication.qgisSettingsDirPath())
for t in (test_registration, test_list, test_install, test_update_plugins, test_untrusted_catalog):
    try:
        t()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILS.append(t.__name__ + " (exception)")

app.exitQgis()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("ALL PASSED" if not FAILS else "FAILED: " + ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
