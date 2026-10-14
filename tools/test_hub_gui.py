# -*- coding: utf-8 -*-
"""GIS Georgia Hub inside a REAL QGIS window (throw-away profile, no network needed).

    qgis-bin.exe --profiles-path <tmp> --noplugins --nologo --code tools/test_hub_gui.py

The "server" is local: catalog.json and plugins/*.zip of this repo are served through the
controller's injectable fetcher (same checksum / host checks as in production for the zip
install path). Results go to $HUB_OUT (JSON) and QGIS quits.
"""
import json
import os
import sys
import time
import traceback

ROOT = os.environ.get("HUB_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis import utils  # noqa: E402
from qgis.core import Qgis, QgsApplication, QgsSettings  # noqa: E402
from qgis.PyQt.QtCore import QTimer  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication  # noqa: E402

from gis_georgia_hub import catalog, controller as ctl_mod, installer_core  # noqa: E402
from gis_georgia_hub.dialog import HubDialog  # noqa: E402

OUT = os.environ.get("HUB_OUT", "hub_result.json")
results = []


def check(name, cond, extra=""):
    results.append({"check": name, "ok": bool(cond), "extra": "" if cond else str(extra)})


def pump(until, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if until():
            return True
        time.sleep(0.05)
    return False


def providers():
    return {p.id() for p in QgsApplication.processingRegistry().providers()}


def local_fetch(url):
    """Serve our own catalog.json and zips instead of plugins.qgis.ge."""
    installer_core.check_url(url)  # same https + host rules as production
    clean = url.split("?")[0].split("://", 1)[1].split("/", 1)[1]  # path on the host
    if clean in ("catalog.json", "catalog.json.sig"):
        path = os.path.join(ROOT, clean)
    elif clean.startswith("plugins/"):
        path = os.path.join(ROOT, clean)
    else:  # icons are served from the plugin source folders
        path = os.path.join(ROOT, *clean.split("/"))
    with open(path, "rb") as fh:
        return fh.read()


def run():
    check("QGIS", True, Qgis.version())
    cache = os.path.join(QgsApplication.qgisSettingsDirPath(), "gis_georgia_hub", "catalog.json")
    ctl = ctl_mod.HubController(fetch=local_fetch, cache_path=cache)
    check("no cached catalog on a fresh profile", ctl.catalog is None and not os.path.exists(cache))

    asked = []
    algs = []
    dlg = HubDialog(ctl, iface=utils.iface, confirm=lambda title, text: asked.append(text) or True,
                    process=algs.append)
    dlg.lang = "en"
    ctl.lang = "en"
    dlg.retranslate()
    dlg.show()
    check("window opens empty before the catalog is loaded", dlg.list.count() == 0)

    # --- load catalog -------------------------------------------------------
    loaded = []
    ctl.refresh(done=loaded.append)
    check("catalog loads", pump(lambda: bool(loaded)) and loaded == [True], loaded)
    n = len(ctl.plugins)
    check("catalog cached on disk", os.path.isfile(cache))
    check("list shows every plugin", dlg.list.count() == n and n >= 15, (dlg.list.count(), n))
    pump(lambda: not ctl.is_busy(), 30)  # the icon download runs right after the catalog
    check("status line counts them once idle", "{} / {}".format(n, n) in dlg.status.text(),
          dlg.status.text())

    # --- search / filters ---------------------------------------------------
    dlg.search.setText("cadastre")
    check("search narrows the list", 1 <= dlg.list.count() < n, dlg.list.count())
    dlg.search.setText("")
    dlg.mode.setCurrentIndex(dlg.mode.findData("installed"))
    check("installed filter: only the Hub itself", dlg.list.count() == 1, dlg.list.count())
    dlg.mode.setCurrentIndex(dlg.mode.findData("all"))
    cats = [dlg.category.itemData(i) for i in range(dlg.category.count())]
    check("category list filled", len(cats) > 2, cats)

    def select(pid):
        dlg.search.setText(pid.replace("_", " ") if pid == "gis_georgia_hub" else pid)
        for row in range(dlg.list.count()):
            if dlg.list.item(row).data(__import__("qgis.PyQt.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole) == pid:
                dlg.list.setCurrentRow(row)
                break
        QApplication.processEvents()
        return dlg._current

    # --- language -----------------------------------------------------------
    cur = select("calculate_geometry")
    check("details shown", cur is not None and "Calculate" in dlg.details.toPlainText(),
          dlg.details.toPlainText()[:80])
    en_text = dlg.details.toPlainText()
    dlg.btn_lang.click()
    check("language switches to Georgian", dlg.lang == "ka" and dlg.details.toPlainText() != en_text)
    check("Georgian details mention where to find it", "სად მოვძებნო" in dlg.details.toPlainText())
    shots = os.environ.get("HUB_SHOT")
    if shots:  # optional screenshots of the window (not a check)
        dlg.search.setText("")
        select("owners_analyzer")
        dlg.search.setText("")
        dlg.list.setCurrentRow(1)
        dlg.grab().save(os.path.join(shots, "hub_ka.png"))
    dlg.btn_lang.click()
    if shots:
        dlg.list.setCurrentRow(1)
        dlg.grab().save(os.path.join(shots, "hub_en.png"))

    # --- install ------------------------------------------------------------
    cur = select("calculate_geometry")
    check("install button enabled for a not-installed plugin", dlg.btn_install.isEnabled())
    check("uninstall disabled before install", not dlg.btn_uninstall.isEnabled())
    dlg.btn_install.click()
    check("confirmation shown with name, size and host",
          bool(asked) and "Calculate Geometry" in asked[-1] and "plugins.qgis.ge" in asked[-1], asked)
    check("install finishes", pump(lambda: installer_core.installed_version("calculate_geometry")
                                   and not ctl.is_busy()))
    check("plugin running and its Processing provider registered",
          utils.isPluginLoaded("calculate_geometry") and "calculate_geometry" in providers(),
          providers())
    check("state is Installed in the controller",
          ctl.state(cur) == catalog.INSTALLED, ctl.state(cur))
    QApplication.processEvents()
    check("buttons follow the new state", dlg.btn_uninstall.isEnabled() and not dlg.btn_install.isEnabled())

    # --- open an algorithm from the details ---------------------------------
    dlg._on_link(__import__("qgis.PyQt.QtCore", fromlist=["QUrl"]).QUrl("alg:calculate_geometry:calculate_geometry"))
    check("algorithm link is handled", algs == ["calculate_geometry:calculate_geometry"], algs)

    # --- disable / enable ---------------------------------------------------
    dlg.btn_toggle.click()
    check("disable unloads the plugin", not utils.isPluginLoaded("calculate_geometry")
          and "calculate_geometry" not in providers())
    dlg.btn_toggle.click()
    check("enable starts it again", utils.isPluginLoaded("calculate_geometry")
          and "calculate_geometry" in providers())

    # --- update detection ---------------------------------------------------
    meta = os.path.join(installer_core.plugins_dir(), "calculate_geometry", "metadata.txt")
    txt = open(meta, encoding="utf-8").read()
    open(meta, "w", encoding="utf-8").write(txt.replace("version=", "version=0.0.", 1))
    check("older installed version is flagged as update",
          [p["id"] for p in ctl.pending_updates()] == ["calculate_geometry"], ctl.pending_updates())
    dlg.reload()
    dlg.mode.setCurrentIndex(dlg.mode.findData("updates"))
    check("updates filter lists it", dlg.list.count() == 1, dlg.list.count())

    # --- plugin shell: menu, first-run question, start-up update notice -----
    from gis_georgia_hub.plugin import GisGeorgiaHubPlugin
    shell = GisGeorgiaHubPlugin(utils.iface)
    shell.initGui()
    check("shell: menu action and toolbar entry created", shell.action is not None
          and shell._timer is not None and shell._timer.isActive())
    shell._timer.stop()
    questions = []
    shell._ask_repo = lambda lang: questions.append(lang) or False
    s2 = QgsSettings()
    s2.setValue("gis_georgia_hub/check_updates", False)
    shell._startup()
    check("shell: asks about the repository once, 'No' registers nothing",
          len(questions) == 1 and not ctl_mod.repository_registered(s2))
    shell._startup()
    check("shell: never asks twice", len(questions) == 1)
    shell._after_startup_refresh(True)
    item = utils.iface.messageBar().currentItem()
    check("shell: update notice names the plugin", item is not None
          and "Calculate" in (item.text() or ""), item.text() if item else None)
    shell._after_startup_refresh(False)  # a failed refresh must stay silent
    shell.unload()
    check("shell: unload removes the action", shell.action is None and shell.ctl is None)
    s2.setValue("gis_georgia_hub/check_updates", True)
    dlg.mode.setCurrentIndex(dlg.mode.findData("all"))
    cur = select("calculate_geometry")
    check("button says Update", dlg.btn_install.text() == "Update", dlg.btn_install.text())
    dlg.btn_install.click()
    check("update finishes", pump(lambda: not ctl.is_busy()
                                  and installer_core.installed_version("calculate_geometry") == cur["version"]))
    check("after the update: no pending updates and still one provider",
          not ctl.pending_updates() and sum(1 for p in QgsApplication.processingRegistry().providers()
                                            if p.id() == "calculate_geometry") == 1)

    # --- uninstall ----------------------------------------------------------
    dlg.btn_uninstall.click()
    check("uninstall removes files and provider",
          installer_core.installed_version("calculate_geometry") is None
          and "calculate_geometry" not in providers())

    # --- icons ----------------------------------------------------------------
    check("icons were downloaded into the profile cache",
          pump(lambda: os.path.isdir(ctl.icon_dir) and len(os.listdir(ctl.icon_dir)) >= 8, 30),
          os.listdir(ctl.icon_dir) if os.path.isdir(ctl.icon_dir) else None)
    with_icon = [p for p in ctl.plugins if ctl.icon_for(p) is not None]
    check("icon_for returns real icons for plugins that have one", len(with_icon) >= 8, len(with_icon))
    check("a plugin without an icon file falls back to the emoji",
          ctl.icon_for(next(p for p in ctl.plugins if p["id"] == "postgis_manager")) is None)
    check("no cached 404 pages", all(os.path.getsize(os.path.join(ctl.icon_dir, f)) > 20
                                     for f in os.listdir(ctl.icon_dir)))

    # --- update all -----------------------------------------------------------
    pre = {}
    for pid in ("owners_analyzer", "transliterator"):
        e = next(p for p in ctl.plugins if p["id"] == pid)
        got = []
        ctl.install(e, done=got.append)
        pump(lambda: bool(got))
        mp = os.path.join(installer_core.plugins_dir(), pid, "metadata.txt")
        txt = open(mp, encoding="utf-8").read()
        open(mp, "w", encoding="utf-8").write(txt.replace("version=", "version=0.0.", 1))
        pre[pid] = e["version"]
    dlg.reload()
    pend = sorted(p["id"] for p in ctl.pending_updates())
    check("two outdated plugins are pending",
          {"owners_analyzer", "transliterator"} <= set(pend), pend)
    check("Update all button shows the count and is enabled",
          str(len(pend)) in dlg.btn_update_all.text() and dlg.btn_update_all.isEnabled(),
          dlg.btn_update_all.text())
    asked.clear()
    dlg.btn_update_all.click()
    check("update all asks once and lists the plugins",
          len(asked) == 1 and "Transliterator" in asked[0] and asked[0].count("•") >= 2, asked)
    check("update all finishes: nothing pending, versions current",
          pump(lambda: not ctl.is_busy() and not ctl.pending_updates()
               and installer_core.installed_version("owners_analyzer") == pre["owners_analyzer"], 90),
          [p["id"] for p in ctl.pending_updates()])
    check("update all button disabled when nothing is pending", not dlg.btn_update_all.isEnabled())
    for pid in ("owners_analyzer", "transliterator"):
        installer_core.uninstall(pid)

    # --- tampered download is refused ---------------------------------------
    bad = dict(cur)
    bad["download"] = dict(cur["download"], sha256="f" * 64)
    done = []
    ctl.install(bad, done=done.append)
    check("checksum mismatch is refused and nothing is installed",
          pump(lambda: bool(done)) and done == [False]
          and installer_core.installed_version("calculate_geometry") is None, done)

    # --- offline: cached copy is used ---------------------------------------
    def broken(url):
        raise installer_core.InstallError("offline")

    ctl2 = ctl_mod.HubController(fetch=broken, cache_path=cache)
    check("cached catalog is available offline", ctl2.catalog is not None and len(ctl2.plugins) == n)
    errs = []
    ctl2.catalogError.connect(lambda e, have: errs.append((e, have)))
    ctl2.refresh()
    check("failed refresh reports the error and keeps the copy",
          pump(lambda: bool(errs)) and errs[0][1] is True and len(ctl2.plugins) == n, errs)

    # --- signature ------------------------------------------------------------
    def tampered(url):
        data = local_fetch(url)
        return data.replace(b"GIS", b"gis", 1) if url.endswith("catalog.json") else data

    def unsigned(url):
        if url.endswith(".sig"):
            raise installer_core.InstallError("404")
        return local_fetch(url)

    def other_key(url):
        data = local_fetch(url)
        if url.endswith(".sig"):
            doc = json.loads(data)
            doc["key_id"] = "deadbeef"
            return json.dumps(doc).encode()
        return data

    before = open(cache, "rb").read()
    for label, fetcher, needle in (("altered catalog", tampered, "does not match"),
                                   ("unsigned catalog", unsigned, "404"),
                                   ("unknown signing key", other_key, "unknown key")):
        c3 = ctl_mod.HubController(fetch=fetcher, cache_path=cache)
        errs = []
        c3.catalogError.connect(lambda e, have, errs=errs: errs.append((e, have)))
        c3.refresh()
        check("refuses an " + label if label != "unsigned catalog" else "refuses an unsigned catalog",
              pump(lambda errs=errs: bool(errs)) and needle in errs[0][0] and errs[0][1] is True, errs)
    check("a refused catalog never replaces the cache", open(cache, "rb").read() == before)

    with open(cache, "a", encoding="utf-8") as fh:  # tamper with the offline copy
        fh.write(" ")
    c4 = ctl_mod.HubController(fetch=broken, cache_path=cache)
    check("an edited offline copy is not trusted", c4.catalog is None)
    with open(cache, "wb") as fh:
        fh.write(before)
    check("the intact offline copy is trusted again",
          ctl_mod.HubController(fetch=broken, cache_path=cache).catalog is not None)

    # --- repository registration --------------------------------------------
    s = QgsSettings()
    check("repository not registered yet", not ctl_mod.repository_registered(s))
    check("register adds it", ctl_mod.register_repository(s) is True and ctl_mod.repository_registered(s))
    check("register twice is a no-op", ctl_mod.register_repository(s) is False)
    check("keys are the ones the Plugin Manager reads",
          s.value("app/plugin_repositories/GIS GEORGIA/url", "", str) == ctl_mod.REPO_URL
          and s.value("app/plugin_repositories/GIS GEORGIA/enabled", False, bool))

    # --- self entry is protected --------------------------------------------
    me = select("gis_georgia_hub")
    check("the Hub cannot install/uninstall itself from its own list",
          me is not None and not dlg.btn_install.isEnabled() and not dlg.btn_uninstall.isEnabled())
    dlg.close()


try:
    run()
except Exception:  # noqa: BLE001
    results.append({"check": "exception", "ok": False, "extra": traceback.format_exc()})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)
QTimer.singleShot(500, QgsApplication.quit)
