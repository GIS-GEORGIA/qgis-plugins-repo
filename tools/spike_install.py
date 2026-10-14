# -*- coding: utf-8 -*-
"""Phase-0 spike: exercise gis_georgia_hub.installer_core inside a REAL QGIS window.

Run with the QGIS GUI binary and a throw-away profile (nothing of yours is touched):

    qgis-bin.exe --profiles-path <tmp> --noplugins --nologo --code tools/spike_install.py

Results are written to the file in $SPIKE_OUT (default: spike_result.json) and QGIS quits.
"""
import io
import json
import os
import sys
import traceback
import zipfile

ROOT = os.environ.get("SPIKE_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis import utils  # noqa: E402
from qgis.core import Qgis, QgsApplication  # noqa: E402
from qgis.PyQt.QtCore import QTimer  # noqa: E402

from gis_georgia_hub import installer_core as ic  # noqa: E402

OUT = os.environ.get("SPIKE_OUT", "spike_result.json")
results = []


def check(name, cond, extra=""):
    results.append({"check": name, "ok": bool(cond), "extra": "" if cond else str(extra)})


def providers():
    return {p.id() for p in QgsApplication.processingRegistry().providers()}


def run():
    check("QGIS", True, Qgis.version())
    check("profile plugin dir is inside the temp profile",
          "profiles" in ic.plugins_dir().replace("\\", "/"), ic.plugins_dir())

    zpath = os.path.join(ROOT, "plugins", "calculate_geometry.zip")
    data = open(zpath, "rb").read()
    sha = ic.sha256_hex(data)
    pid, ver = ic.inspect_zip(data, "calculate_geometry")
    check("inspect_zip reads id and version", pid == "calculate_geometry" and ver, (pid, ver))

    # bad inputs change nothing
    for label, bad, kwargs, needle in (
        ("checksum mismatch", data, {"expected_sha256": "0" * 64}, "Checksum"),
        ("wrong plugin folder", data, {"expected_id": "other"}, "Unexpected"),
    ):
        try:
            ic.install_zip(bad, **kwargs)
            check("rejects " + label, False, "no error")
        except ic.InstallError as exc:
            check("rejects " + label, needle in str(exc), exc)

    def zip_with(names):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for n in names:
                zf.writestr(n, "x")
        return buf.getvalue()

    for label, names in (("zip-slip path", ["p/metadata.txt", "p/../../evil.py"]),
                         ("two folders", ["a/metadata.txt", "b/metadata.txt"]),
                         ("no metadata", ["p/x.py"]),
                         ("absolute path", ["/etc/x"])):
        try:
            ic.inspect_zip(zip_with(names))
            check("rejects " + label, False, "no error")
        except ic.InstallError:
            check("rejects " + label, True)
    check("nothing installed by the bad attempts",
          ic.installed_version("calculate_geometry") is None)

    # install
    res = ic.install_zip(data, expected_id="calculate_geometry", expected_sha256=sha)
    check("install: files in place", ic.installed_version("calculate_geometry") == ver)
    check("install: plugin started", res.started and utils.isPluginLoaded("calculate_geometry"),
          (res, utils.active_plugins))
    check("install: Processing provider registered", "calculate_geometry" in providers(), providers())
    check("install: first install has no previous version", res.previous_version is None)

    # update over a running plugin
    res2 = ic.install_zip(data, expected_id="calculate_geometry")
    check("update: previous version reported", res2.previous_version == ver, res2)
    check("update: still running, one provider",
          utils.isPluginLoaded("calculate_geometry")
          and sum(1 for p in QgsApplication.processingRegistry().providers()
                  if p.id() == "calculate_geometry") == 1, providers())
    check("update: no leftover backup folder",
          not os.path.exists(os.path.join(ic.plugins_dir(), "calculate_geometry.gg_bak")))

    # real download from the live site
    try:
        live = ic.download("https://plugins.qgis.ge/plugins/transliterator.zip")
        lid, lver = ic.inspect_zip(live, "transliterator")
        check("download from plugins.qgis.ge and inspect", lid == "transliterator" and lver, (lid, lver))
        r3 = ic.install_zip(live, expected_id="transliterator", expected_sha256=ic.sha256_hex(live))
        check("live plugin installed and started", r3.started and "transliterator" in providers(),
              (r3, providers()))
    except Exception as exc:  # noqa: BLE001
        check("download from plugins.qgis.ge", False, repr(exc))
    for url in ("http://plugins.qgis.ge/x.zip", "https://example.com/x.zip"):
        try:
            ic.download(url)
            check("refuses " + url, False, "no error")
        except ic.InstallError:
            check("refuses " + url, True)

    # uninstall
    check("uninstall returns True", ic.uninstall("calculate_geometry"))
    check("uninstall: files gone", ic.installed_version("calculate_geometry") is None)
    check("uninstall: provider gone", "calculate_geometry" not in providers(), providers())
    check("uninstall of a missing plugin returns False", ic.uninstall("calculate_geometry") is False)
    ic.uninstall("transliterator")


try:
    run()
except Exception:  # noqa: BLE001
    results.append({"check": "exception", "ok": False, "extra": traceback.format_exc()})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)
QTimer.singleShot(500, QgsApplication.quit)
