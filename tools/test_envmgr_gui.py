# -*- coding: utf-8 -*-
"""QGIS Environment Manager inside a REAL QGIS window (throw-away profile, no network, nothing installed):

    qgis-bin.exe --profiles-path <tmp> --noplugins --nologo --code tools/test_envmgr_gui.py

Linux-only behaviour (package installation) is driven with stubbed facts and a stubbed step runner: this
machine cannot run a system-QGIS-on-Linux inside the test, so the real apt/dnf/... run is covered by the
qgis-installer container tests, and what is checked here is the window around it. Results -> $ENVMGR_OUT.
"""
import json
import os
import sys
import tempfile
import time
import traceback

ROOT = os.environ.get("ENVMGR_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from qgis import utils  # noqa: E402
from qgis.core import Qgis, QgsApplication  # noqa: E402
from qgis.PyQt.QtCore import QTimer  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication  # noqa: E402

from qgis_environment_manager import diagnostics  # noqa: E402
from qgis_environment_manager.dialog import EnvDialog  # noqa: E402
from qgis_environment_manager.qgis_installer import requirements  # noqa: E402

OUT = os.environ.get("ENVMGR_OUT", "envmgr_result.json")
results = []


def check(name, cond, extra=""):
    results.append({"check": name, "ok": bool(cond), "extra": "" if cond else str(extra)})


def pump(until, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        QApplication.processEvents()
        if until():
            return True
        time.sleep(0.03)
    return False


def make_plugin(base, folder, **meta):
    os.makedirs(os.path.join(base, folder))
    lines = ["[general]"] + ["{}={}".format(k, v) for k, v in meta.items()]
    with open(os.path.join(base, folder, "metadata.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


FACTS = {"qgis_version": "3.44.5", "qgis_release": "Solothurn", "python": "3.12.1", "qt": "5.15.13",
         "os": "Linux-test", "is_linux": True, "runtime": "native", "prefix": "/usr",
         "profile": "/home/u/.local/share/QGIS/QGIS3/profiles/default", "gdal": "3.10.0"}


def run():
    check("QGIS", True, Qgis.version())
    tmp = tempfile.mkdtemp(prefix="envmgr_")
    plugins = os.path.join(tmp, "plugins")
    make_plugin(plugins, "fits_both", name="Fits Both", version="1.0", qgisMinimumVersion="3.40",
                qgisMaximumVersion="4.99", supportsQt6="True")
    make_plugin(plugins, "only_qgis3", name="Only QGIS 3", version="2.1", qgisMinimumVersion="3.0")
    make_plugin(plugins, "no_qt6_flag", name="No Qt6 Flag", version="0.5", qgisMinimumVersion="3.40",
                qgisMaximumVersion="4.99")
    make_plugin(plugins, "postgis_manager", name="PostGIS Manager", version="1.3.1", qgisMinimumVersion="3.40",
                qgisMaximumVersion="4.99", supportsQt6="True")
    make_plugin(plugins, "photo_geotagger", name="Photo Geotagger", version="0.8.0", qgisMinimumVersion="3.40",
                qgisMaximumVersion="4.99", supportsQt6="True")

    # ---- real facts from the running QGIS ------------------------------------
    real = diagnostics.gather_facts()
    check("real facts: version matches Qgis.version()", real["qgis_version"] == Qgis.version().split("-")[0], real)
    check("real facts: python, qt, profile, runtime present",
          all(real.get(k) for k in ("python", "qt", "profile", "prefix", "runtime", "os")), real)
    check("real facts: this profile is the temporary one", "profiles" in real["profile"].replace("\\", "/"))

    missing = {"pgclient", "exiftool"}
    present = lambda rid, **kw: rid not in missing  # noqa: E731
    orig_present = requirements.is_present
    requirements.is_present = present
    confirms, runs = [], []

    def fake_steps(steps, on_line=None, elevate=("pkexec",), geteuid=None):
        runs.append((steps, list(elevate)))
        for line in ("Reading package lists...\n", "Setting up postgresql-client\n"):
            on_line(line)
        missing.clear()                     # "the packages are now installed"
        return 0, None

    dlg = EnvDialog(utils.iface, confirm=lambda title, text: confirms.append(text) or True,
                    run_steps=fake_steps, facts_fn=lambda: dict(FACTS), dirs_fn=lambda: [plugins],
                    sysinfo={"pm": "apt-get"}, load_installs=False)
    dlg.lang = "en"
    dlg.refresh()
    dlg.show()

    # ---- diagnostics ----------------------------------------------------------
    text = dlg.diag.toPlainText()
    check("diagnostics show the version, release name and Python", "3.44.5 (Solothurn)" in text and "3.12.1" in text, text[:200])
    check("diagnostics: LTR line and 'QGIS 4 is available' notes", "long-term (LTR) line 3.44" in text and "QGIS 4" in text, text)
    check("diagnostics: install list is explained when not loaded", "Checking" in text)

    # ---- plugins tab ----------------------------------------------------------
    t = dlg.table
    names = [t.item(i, 0).text() for i in range(t.rowCount())]
    check("table lists the five plugins sorted by name", names == ["Fits Both", "No Qt6 Flag", "Only QGIS 3", "Photo Geotagger", "PostGIS Manager"], names)
    cell = lambda name, col: t.item(names.index(name), col).text()  # noqa: E731
    check("fits both: declared on QGIS 4", "declared" in cell("Fits Both", 5) and cell("Fits Both", 3) == "yes")
    check("no Qt 6 flag: needs checking on QGIS 4, fine on QGIS 3",
          "not declared" in cell("No Qt6 Flag", 5) and cell("No Qt6 Flag", 4).startswith("✔"))
    check("only QGIS 3: not for QGIS 4 (maximum assumed 3.99)", cell("Only QGIS 3", 5) == "✖ no" and "3.99" in cell("Only QGIS 3", 2), cell("Only QGIS 3", 2))
    check("the reason is in the tooltip", "limited to QGIS" in t.item(names.index("Only QGIS 3"), 5).toolTip(), t.item(names.index("Only QGIS 3"), 5).toolTip())
    check("summary counts", "3 declare support, 1 do not declare Qt 6, 1 are limited" in dlg.pl_summary.text(), dlg.pl_summary.text())
    dlg.chk_only.setChecked(True)
    check("only-problems filter hides the ones that are fine", t.rowCount() == 2, t.rowCount())
    dlg.chk_only.setChecked(False)

    shots = os.environ.get("ENVMGR_SHOT")
    if shots:  # optional screenshots of the three tabs (not a check)
        for i, name in enumerate(("diag", "plugins", "requirements")):
            dlg.tabs.setCurrentIndex(i)
            QApplication.processEvents()
            dlg.grab().save(os.path.join(shots, "env_{}_en.png".format(name)))
        dlg.tabs.setCurrentIndex(0)

    # ---- language ---------------------------------------------------------------
    dlg.btn_lang.click()
    if shots:
        for i, name in enumerate(("diag", "plugins", "requirements")):
            dlg.tabs.setCurrentIndex(i)
            QApplication.processEvents()
            dlg.grab().save(os.path.join(shots, "env_{}_ka.png".format(name)))
        dlg.tabs.setCurrentIndex(0)
    check("Georgian: tab titles and table header change", dlg.lang == "ka" and dlg.tabs.tabText(2) == "მოთხოვნები"
          and t.horizontalHeaderItem(0).text() == "დანამატი", dlg.tabs.tabText(2))
    check("Georgian diagnostics", "ვერსია" in dlg.diag.toPlainText())
    dlg.btn_lang.click()
    check("back to English", dlg.tabs.tabText(2) == "Requirements")

    # ---- requirements tab -----------------------------------------------------
    tree = dlg.rq_tree
    tops = [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]
    check("requirements: only the installed GIS GEORGIA plugins that need something", tops == ["Photo Geotagger", "PostGIS Manager"] or
          sorted(tops) == ["Photo Geotagger", "PostGIS Manager"], tops)
    flat = " | ".join(tree.topLevelItem(i).child(j).text(0) for i in range(tree.topLevelItemCount())
                      for j in range(tree.topLevelItem(i).childCount()))
    check("requirements: states and package names shown", "[missing] PostgreSQL client tools" in flat and "postgresql-client" in flat
          and "[installed] PostgreSQL driver" in flat, flat)
    check("install button enabled (required ones missing)", dlg.btn_install.isEnabled(), dlg.rq_note.text())
    dlg.btn_install.click()
    check("the commands are shown for review before anything runs",
          len(confirms) == 1 and "apt-get install -y postgresql-client" in confirms[0] and "exiftool" not in confirms[0], confirms)
    check("steps ran through the elevator as root steps",
          pump(lambda: bool(runs)) and runs[0][0][0]["root"] is True and runs[0][1] in (["pkexec"], ["sudo"]), runs)
    check("output streamed into the log and the run finished",
          pump(lambda: "Finished" in dlg.log.toPlainText()), dlg.log.toPlainText())
    check("log has the command output", "Setting up postgresql-client" in dlg.log.toPlainText())
    pump(lambda: not (dlg.worker and dlg.worker.isRunning()))
    flat = " | ".join(tree.topLevelItem(i).child(j).text(0) for i in range(tree.topLevelItemCount())
                      for j in range(tree.topLevelItem(i).childCount()))
    check("after the install the list refreshes: nothing missing, install disabled again",
          "[missing]" not in flat and "already installed" in dlg.rq_note.text() and not dlg.btn_install.isEnabled(),
          (flat, dlg.rq_note.text()))

    # optional ones included
    missing.update({"exiftool"})
    dlg.refresh()
    check("optional ones are not installed unless asked", not dlg.btn_install.isEnabled() and "installed" in dlg.rq_note.text(), dlg.rq_note.text())
    dlg.chk_optional.setChecked(True)
    check("ticking 'include the optional ones' enables the install", dlg.btn_install.isEnabled())
    confirms.clear()
    dlg.btn_install.click()
    check("optional package is in the reviewed commands", confirms and "libimage-exiftool-perl" in confirms[0], confirms)
    pump(lambda: not (dlg.worker and dlg.worker.isRunning()))
    dlg.chk_optional.setChecked(False)

    # failures: a step fails / elevation not possible
    def failing(steps, on_line=None, elevate=("pkexec",), geteuid=None):
        on_line("E: could not lock\n")
        return 100, steps[0]

    def no_elevator(steps, on_line=None, elevate=("pkexec",), geteuid=None):
        return 127, steps[0]

    missing.update({"pgclient"})
    for fn, needle in ((failing, "exit code 100"), (no_elevator, "sudo sh ")):
        dlg._run_steps = fn
        dlg.refresh()
        dlg.btn_install.click()
        check("failure is reported: " + needle, pump(lambda n=needle: n in dlg.log.toPlainText()), dlg.log.toPlainText())
        pump(lambda: not (dlg.worker and dlg.worker.isRunning()))

    # blockers
    for label, facts, pm, needle in (
            ("flatpak QGIS", dict(FACTS, runtime="flatpak"), "apt-get", "sandboxed (flatpak)"),
            ("not Linux", dict(FACTS, is_linux=False, runtime="native"), "", "only works on Linux"),
            ("no package manager", dict(FACTS), "", "No supported package manager")):
        d2 = EnvDialog(utils.iface, facts_fn=lambda f=facts: dict(f), dirs_fn=lambda: [plugins], sysinfo={"pm": pm},
                       load_installs=False)
        d2.lang = "en"
        d2.refresh()
        check("install blocked: " + label, not d2.btn_install.isEnabled() and needle in d2.rq_note.text(), d2.rq_note.text())
        d2.close()
    d3 = EnvDialog(utils.iface, facts_fn=lambda: dict(FACTS), dirs_fn=lambda: [os.path.join(tmp, "empty")],
                   sysinfo={"pm": "apt-get"}, load_installs=False)
    d3.lang = "en"
    d3.refresh()
    check("no plugins in the profile: friendly text, install disabled", not d3.btn_install.isEnabled()
          and "No plugins" in d3.pl_summary.text() and "none of the installed" in d3.rq_note.text().lower(), (d3.pl_summary.text(), d3.rq_note.text()))
    d3.close()

    # ---- copy report -------------------------------------------------------------
    report = dlg.report()
    check("the report is plain text with facts and findings", "QGIS Environment Manager" in report and "3.44.5" in report
          and "What it means" in report and "<" not in report, report[:200])
    import qgis_environment_manager.dialog as dialog_module
    got = []

    class FakeClipboard:
        def setText(self, text):  # noqa: N802
            got.append(text)

    class FakeApp:
        @staticmethod
        def clipboard():
            return FakeClipboard()

    real_app, dialog_module.QApplication = dialog_module.QApplication, FakeApp
    try:
        dlg.btn_copy.click()
    finally:
        dialog_module.QApplication = real_app
    check("the Copy button hands exactly that report to the clipboard", got == [report], got)
    probe = QApplication.clipboard()
    probe.setText("probe")
    if pump(lambda: probe.text() == "probe", 3):          # the desktop clipboard is usable in this session
        dlg.btn_copy.click()
        check("and the real clipboard receives it", pump(lambda: probe.text() == report, 5), probe.text()[:100])

    # ---- installs worker (real, off the GUI thread) -----------------------------------
    d4 = EnvDialog(utils.iface, facts_fn=lambda: dict(FACTS, is_linux=True), dirs_fn=lambda: [plugins],
                   sysinfo={"pm": "apt-get"}, load_installs=True)
    d4.lang = "en"
    check("the install scan finishes and the text leaves 'Checking'",
          pump(lambda: d4.installs is not None, 60) and "Checking" not in d4.diag.toPlainText(), d4.diag.toPlainText()[-300:])
    d4.close()

    # ---- the plugin shell -----------------------------------------------------------------
    from qgis_environment_manager.plugin import EnvManagerPlugin
    shell = EnvManagerPlugin(utils.iface)
    shell.initGui()
    check("shell: action created", shell.action is not None)
    shell.unload()
    check("shell: unload cleans up", shell.action is None)

    requirements.is_present = orig_present
    dlg.close()


try:
    run()
except Exception:  # noqa: BLE001
    results.append({"check": "exception", "ok": False, "extra": traceback.format_exc()})

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=1)
QTimer.singleShot(500, QgsApplication.quit)
