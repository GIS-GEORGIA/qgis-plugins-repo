# -*- coding: utf-8 -*-
"""Hub against the LIVE site (plugins.qgis.ge) in a real QGIS window, throw-away profile.

    qgis-bin.exe --profiles-path <tmp> --noplugins --nologo --code tools/test_hub_live.py

Not part of CI (needs internet and a QGIS GUI). Results go to $HUB_OUT.
"""
import json
import os
import sys
import time
import traceback

ROOT = os.environ.get("HUB_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis import utils  # noqa: E402
from qgis.core import Qgis, QgsApplication  # noqa: E402
from qgis.PyQt.QtCore import QTimer  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication  # noqa: E402

from gis_georgia_hub import installer_core  # noqa: E402
from gis_georgia_hub.controller import HubController  # noqa: E402

OUT = os.environ.get("HUB_OUT", "hub_live.json")
results = []


def check(name, cond, extra=""):
    results.append({"check": name, "ok": bool(cond), "extra": "" if cond else str(extra)})


def pump(until, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if until():
            return True
        time.sleep(0.05)
    return False


def providers():
    return {p.id() for p in QgsApplication.processingRegistry().providers()}


def run():
    check("QGIS", True, Qgis.version())
    ctl = HubController()  # production defaults: https://plugins.qgis.ge/catalog.json
    check("default catalog URL is the live one", ctl.catalog_url == "https://plugins.qgis.ge/catalog.json")
    done = []
    ctl.refresh(done=done.append)
    check("live catalog loads", pump(lambda: bool(done)) and done == [True], done)
    plugins = ctl.plugins
    check("live catalog has the Hub and 14 other plugins", len(plugins) == 15
          and plugins[0]["id"] == "gis_georgia_hub", len(plugins))
    check("every download is https on plugins.qgis.ge",
          all(p["download"]["url"].startswith("https://plugins.qgis.ge/") for p in plugins))

    by = {p["id"]: p for p in plugins}
    for pid in ("calculate_geometry", "owners_analyzer"):
        entry = by[pid]
        ok = []
        ctl.install(entry, done=ok.append)
        check("live install of " + pid, pump(lambda: bool(ok)) and ok == [True], ok)
        check(pid + " running with its Processing provider",
              utils.isPluginLoaded(pid) and pid in providers(), providers())
        check(pid + " version matches the catalog",
              installer_core.installed_version(pid) == entry["version"])

    # the published Hub zip itself: install it and start it with the real iface
    hub = by["gis_georgia_hub"]
    data = installer_core.download(hub["download"]["url"])
    check("Hub zip checksum equals the catalog", installer_core.sha256_hex(data) == hub["download"]["sha256"])
    res = installer_core.install_zip(data, expected_id="gis_georgia_hub",
                                     expected_sha256=hub["download"]["sha256"])
    check("published Hub installs and starts", res.started and utils.isPluginLoaded("gis_georgia_hub"), res)
    plugin = utils.plugins.get("gis_georgia_hub")
    check("Hub plugin object has its menu action", plugin is not None and plugin.action is not None)
    if plugin is not None and plugin._timer is not None:
        plugin._timer.stop()
    check("catalog sees nothing to update after fresh installs", not ctl.pending_updates(),
          [p["id"] for p in ctl.pending_updates()])

    for pid in ("calculate_geometry", "owners_analyzer"):
        ctl.uninstall(by[pid])
    check("uninstall cleans up", installer_core.installed_version("calculate_geometry") is None
          and "owners_analyzer" not in providers())
    installer_core.uninstall("gis_georgia_hub")
    check("Hub uninstalls", installer_core.installed_version("gis_georgia_hub") is None)


try:
    run()
except Exception:  # noqa: BLE001
    results.append({"check": "exception", "ok": False, "extra": traceback.format_exc()})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)
QTimer.singleShot(500, QgsApplication.quit)
