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
    prof_default = os.path.join(tmp, "profiles", "default")
    for rel, data in (("QGIS/QGIS3.ini", b"[General]\nx=1\n"), ("python/plugins/p/metadata.txt", b"[general]\n"), ("cache/big.bin", b"c" * 400)):
        os.makedirs(os.path.dirname(os.path.join(prof_default, *rel.split("/"))), exist_ok=True)
        with open(os.path.join(prof_default, *rel.split("/")), "wb") as fh:
            fh.write(data)
    FACTS["profile"] = prof_default
    AUTO_DIR = os.path.join(tmp, "auto_backups")
    sims = []

    def sim_stub(steps):
        sims.append(steps)
        return {"items": [{"installs": 2, "upgrades": 0, "downgrades": 1, "remove_count": 0, "removes": [], "download": "1.6 MiB", "disk": None,
                           "tool": "apt", "verb": "install", "names": [], "cmd": ""}], "unsimulated": 0, "warnings": []}
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
                    sysinfo={"pm": "apt-get"}, load_installs=False, simulate_fn=sim_stub)
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
    check("the package manager's simulation is part of what is shown before anything runs",
          sims and "What the package manager says it would do" in confirms[0] and "download 1.6 MiB" in confirms[0], confirms)
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

    # ---- QGIS versions tab ---------------------------------------------------------------
    dlg._run_steps = fake_steps                       # the failure loop above left a failing runner behind
    from qgis_environment_manager.qgis_installer import system as core_system
    import zipfile

    def sysinfo_for(osr, pm, tools=(), immutable="none"):
        path = os.path.join(tmp, "os-release-" + str(len(osr)))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(osr)
        return core_system.detect(path, pm, "amd64", tools={t: True for t in tools}, immutable=immutable)

    UBUNTU = sysinfo_for('NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_ID="24.04"\nVERSION_CODENAME=noble\n'
                         'UBUNTU_CODENAME=noble\nPRETTY_NAME="Ubuntu 24.04 LTS"\n', "apt-get")
    NIXOS = sysinfo_for('ID=nixos\nPRETTY_NAME="NixOS"\n', "")
    vt = dlg.versions
    vt._backup_dir = AUTO_DIR
    dlg.lang = "en"
    vt._info = UBUNTU
    dlg.installs = [{"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "3.44.5", "o": "qgis.org", "root": True}]
    dlg.retranslate()
    check("versions tab is the fifth tab", dlg.tabs.count() == 5 and dlg.tabs.tabText(4) == "QGIS versions", dlg.tabs.tabText(4))
    dlg.btn_lang.click()
    check("Georgian title of the versions tab", dlg.tabs.tabText(4) == "QGIS-ის ვერსიები" and "პროფილ" in vt.btn_backup.text(), dlg.tabs.tabText(3))
    dlg.btn_lang.click()
    check("versions tab: stable goal on Ubuntu recommends the official repository, LTR preselected",
          vt.recipe_id() == "apt-official" and "Official QGIS repository" in vt.lbl_rec.text()
          and vt.opt_cmb["channel"].isVisibleTo(vt) and vt.chan_keys[vt.opt_cmb["channel"].currentIndex()] == "ltr",
          (vt.recipe_id(), vt.lbl_rec.text()))
    check("the official repository changes the system QGIS in place, and says so", "in place" in vt.lbl_where.text(), vt.lbl_where.text())
    check("the other recipes of this system are offered too",
          {"apt-official", "apt-distro", "flatpak"} <= set(vt.recipe_ids), vt.recipe_ids)
    vt.goal_btns["alongside"].setChecked(True)
    check("alongside goal: Flatpak stable, installs apart, branch chooser shown",
          vt.recipe_id() == "flatpak" and "Installs apart" in vt.lbl_where.text()
          and vt.opt_cmb["branch"].isVisibleTo(vt) and vt.opt_cmb["scope"].isVisibleTo(vt)
          and not vt.opt_cmb["channel"].isVisibleTo(vt), (vt.recipe_id(), vt.lbl_where.text()))

    # side by side: one confirmation, runs, no 'in place' question
    confirms.clear()
    runs.clear()
    vt.btn_install.click()
    check("flatpak: the reviewed text names the stable branch and the user scope",
          len(confirms) == 1 and "org.qgis.qgis//stable" in confirms[0] and "--user" in confirms[0], confirms)
    check("flatpak: side by side needs no second question and the steps ran",
          pump(lambda: bool(runs)) and len(confirms) == 1, (len(confirms), runs))
    pump(lambda: not vt._running())
    check("flatpak: the log says it finished", "Finished" in vt.log.toPlainText(), vt.log.toPlainText())

    # the lts branch, the system scope
    vt.opt_cmb["branch"].setCurrentIndex(1)
    vt.opt_cmb["scope"].setCurrentIndex(1)
    confirms.clear()
    runs.clear()
    vt.btn_install.click()
    pump(lambda: bool(runs))
    check("flatpak lts, system scope: both choices reach the commands, with the end-of-life warning",
          confirms and "org.qgis.qgis//lts" in confirms[0] and "--system" in confirms[0] and "end-of-life" in confirms[0], confirms)
    check("flatpak system scope runs as root", runs and runs[0][0][-1]["root"] is True, runs)
    pump(lambda: not vt._running())

    # in place: two confirmations, and a 'no' to the second runs nothing
    vt.goal_btns["stable"].setChecked(True)
    answers = iter([True, False])
    asked = []
    dlg._confirm = lambda title, text: asked.append(title) or next(answers)
    runs.clear()
    vt.btn_install.click()
    QApplication.processEvents()
    check("in place: asked twice (commands, then 'this QGIS is open')", len(asked) == 2 and asked[1] == "This QGIS is open right now", asked)
    check("declining the second question runs nothing", not runs and not vt._running(), runs)
    dlg._confirm = lambda title, text: confirms.append(text) or True

    # update (the earlier run refreshed the window, which forgets the installations: they are "found" again here)
    confirms.clear()
    runs.clear()
    dlg.installs = [{"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "3.44.5", "o": "qgis.org", "root": True}]
    vt.refresh()
    check("update button enabled when an installation was found", vt.btn_update.isEnabled(), vt.lbl_update.text())
    vt.btn_update.click()
    check("update: the exact installed packages, then the close-QGIS warning",
          confirms and "apt-get install -y --only-upgrade python3-qgis qgis" in confirms[0] and "Close QGIS" in confirms[0], confirms)
    check("update is in place: second confirmation too and then it ran", pump(lambda: bool(runs)) and len(confirms) == 2, (len(confirms), runs))
    pump(lambda: not vt._running())
    dlg.installs = []
    vt.refresh()
    check("nothing installed: update disabled with an explanation", not vt.btn_update.isEnabled() and "Nothing to update" in vt.lbl_update.text(), vt.lbl_update.text())
    dlg.installs = None
    vt.refresh()
    check("installs still loading: says so", "Checking" in vt.lbl_update.text() and not vt.btn_update.isEnabled(), vt.lbl_update.text())

    # installed QGIS programs: the table, the update check, starting one
    from qgis_environment_manager.qgis_installer import instances as core_instances
    have = lambda *names: (lambda c: "/usr/bin/" + c if c in names else None)  # noqa: E731
    FP_STABLE = {"kind": "flatpak", "i": "user", "v": "4.2.2", "br": "stable", "root": False}
    FP_LTS = {"kind": "flatpak", "i": "system", "v": "3.44.5", "br": "lts", "root": True}
    APT = {"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "3.44.5", "o": "qgis.org", "root": True}
    SNAP = {"kind": "snap", "v": "3.44", "root": True}
    dlg.installs = [APT, FP_STABLE, FP_LTS, SNAP]
    vt.instance_rows = lambda: core_instances.list_instances(dlg.installs, which=have("qgis", "flatpak"))   # snap cannot be started here
    vt.retranslate()
    tbl = vt.inst_table
    cell = lambda r, c: tbl.item(r, c).text()  # noqa: E731
    check("the table lists every installation with its version and how it starts",
          tbl.rowCount() == 4 and "apt packages" in cell(0, 0) and cell(0, 1) == "3.44.5" and cell(0, 3) == "qgis"
          and "user, stable" in cell(1, 0) and cell(1, 3) == "flatpak run --branch=stable org.qgis.qgis"
          and cell(2, 3) == "flatpak run --branch=lts org.qgis.qgis", [(cell(r, 0), cell(r, 3)) for r in range(tbl.rowCount())])
    check("one that cannot be started says so", cell(3, 3) == "No way to start this one is known.", cell(3, 3))
    check("before the check the update column is empty", all(cell(r, 2) == "" for r in range(4)))

    vt._check_fn = lambda items: [{"id": "apt", "version": "3.44.5", "update": True, "candidate": "3.44.6", "source": "cached"},
                                  {"id": "flatpak-user-stable", "version": "4.2.2", "update": None, "candidate": None, "source": "network"},
                                  {"id": "flatpak-system-lts", "version": "3.44.5", "update": False, "candidate": None, "source": "network"}]
    vt.btn_check.click()
    check("the update check runs in the background and fills the column",
          pump(lambda: cell(0, 2) != ""), [cell(r, 2) for r in range(4)])
    pump(lambda: not (vt._updates_worker and vt._updates_worker.isRunning()))
    check("a newer build is shown with its version; unknown is not 'up to date'; current is current",
          cell(0, 2) == "newer build available (3.44.6)" and cell(1, 2) == "could not tell" and cell(2, 2) == "up to date",
          [cell(r, 2) for r in range(4)])
    check("the source of the answer is in the tooltip", "last refresh" in tbl.item(0, 2).toolTip() and "online" in tbl.item(1, 2).toolTip(),
          (tbl.item(0, 2).toolTip(), tbl.item(1, 2).toolTip()))
    check("the check button is usable again", vt.btn_check.isEnabled())

    started = []

    class P:
        pid = 99

    vt._popen = lambda argv, **kw: started.append((argv, kw)) or P()
    confirms.clear()
    vt.log.clear()
    tbl.selectRow(0)
    vt.btn_start.click()
    check("starting a system QGIS shows the command and the shared-profile warning first",
          confirms and "qgis" in confirms[0] and "share your profile folder" in confirms[0], confirms)
    check("then starts it detached", started and started[0][0] == ["qgis"] and started[0][1]["start_new_session"] is True, started)
    check("and logs the process", "Started (process 99)" in vt.log.toPlainText(), vt.log.toPlainText())
    started.clear()
    confirms.clear()
    tbl.selectRow(1)
    vt.btn_start.click()
    check("a Flatpak has its own profile: no warning, the branch is in the command",
          confirms and "flatpak run --branch=stable org.qgis.qgis" in confirms[0] and "share your profile" not in confirms[0]
          and started and started[0][0][:3] == ["flatpak", "run", "--branch=stable"], (confirms, started))
    started.clear()
    dlg._confirm = lambda title, text: False
    tbl.selectRow(0)
    vt.btn_start.click()
    check("declining the question starts nothing", started == [], started)
    dlg._confirm = lambda title, text: confirms.append(text) or True
    vt.log.clear()
    tbl.selectRow(3)
    vt.btn_start.click()
    check("an installation that cannot be started starts nothing and says what to do", started == [] and "Pick a QGIS" in vt.log.toPlainText(), vt.log.toPlainText())
    tbl.clearSelection()
    tbl.setCurrentCell(-1, -1)
    vt.log.clear()
    vt.btn_start.click()
    check("nothing selected: the same hint", started == [] and "Pick a QGIS" in vt.log.toPlainText(), vt.log.toPlainText())
    dlg.btn_lang.click()
    check("Georgian headers of the installed-programs table", list(tbl.horizontalHeaderItem(i).text() for i in range(4))[:2] == ["QGIS", "ვერსია"], tbl.horizontalHeaderItem(1).text())
    dlg.btn_lang.click()
    del vt.instance_rows                              # back to the real method
    dlg.installs = None
    vt.refresh()

    # instructions-only recipes run nothing
    vt._info = NIXOS
    vt.retranslate()
    confirms.clear()
    runs.clear()
    check("NixOS: the recipe is instructions only", vt.recipe_id() == "nix-manual", vt.recipe_id())
    vt.btn_install.click()
    QApplication.processEvents()
    check("NixOS: instructions shown, nothing run", confirms and "nix-shell -p" in confirms[0] and not runs, (confirms, runs))

    # blockers
    for label, facts, needle in (("flatpak QGIS", dict(FACTS, runtime="flatpak"), "sandboxed (flatpak)"),
                                 ("not Linux", dict(FACTS, is_linux=False), "only works on Linux")):
        d5 = EnvDialog(utils.iface, facts_fn=lambda f=facts: dict(f), dirs_fn=lambda: [plugins], sysinfo={"pm": "apt-get"},
                       load_installs=False)
        d5.lang = "en"
        d5.versions._info = UBUNTU
        d5.installs = [{"kind": "apt", "pkgs": ["qgis"], "v": "3.44.5", "o": "", "root": True}]
        d5.retranslate()
        check("versions blocked: " + label, not d5.versions.btn_update.isEnabled() and not d5.versions.btn_install.isEnabled()
              and needle in d5.versions.blocker.text(), d5.versions.blocker.text())
        d5.close()

    # profile backup
    prof = os.path.join(tmp, "profile")
    for rel, data in (("QGIS/QGIS3.ini", b"[General]\n"), ("python/plugins/x/metadata.txt", b"[general]\n"), ("cache/c.bin", b"c" * 500)):
        os.makedirs(os.path.dirname(os.path.join(prof, *rel.split("/"))), exist_ok=True)
        with open(os.path.join(prof, *rel.split("/")), "wb") as fh:
            fh.write(data)
    dlg.facts["profile"] = prof
    out_dir = os.path.join(tmp, "backups")
    vt._pick_dir = lambda profile: out_dir
    vt.log.clear()
    vt.btn_backup.click()
    zips = [f for f in os.listdir(out_dir)] if os.path.isdir(out_dir) else []
    check("backup: one zip appears and the log reports it", len(zips) == 1 and "Copy ready" in vt.log.toPlainText(), (zips, vt.log.toPlainText()))
    if zips:
        with zipfile.ZipFile(os.path.join(out_dir, zips[0])) as zf:
            names = sorted(n.replace("\\", "/") for n in zf.namelist())
        check("backup: settings and plugins in, cache out", names == ["profile/QGIS/QGIS3.ini", "profile/python/plugins/x/metadata.txt"], names)
    vt._pick_dir = lambda profile: os.path.join(profile, "QGIS")
    vt.log.clear()
    vt.btn_backup.click()
    check("backup into the profile itself is refused", "Could not make the copy" in vt.log.toPlainText(), vt.log.toPlainText())
    vt._pick_dir = lambda profile: ""
    vt.log.clear()
    vt.btn_backup.click()
    check("cancelling the folder chooser does nothing", vt.log.toPlainText() == "", vt.log.toPlainText())
    dlg.facts["profile"] = FACTS["profile"]
    vt._pick_dir = None

    # ---- the automatic copy before QGIS is changed, the simulation, other versions, keeping, restoring -------
    import zipfile as zf_mod
    from qgis_environment_manager import profile_backup as pbk
    from qgis_environment_manager.qgis_installer import versions as core_versions
    APT2 = {"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "1:3.44.5+24noble", "o": "qgis.org", "root": True}
    FP2 = {"kind": "flatpak", "i": "user", "v": "4.2.2", "br": "stable", "root": False}
    dlg.facts["profile"] = FACTS["profile"]
    vt._info = UBUNTU
    vt.updates, vt.locks = {}, {}
    vt.instance_rows = lambda: core_instances.list_instances(dlg.installs or [], which=have("qgis", "flatpak"))

    def reset():
        """Every finished run refreshes the window, which forgets the installations (the real one finds them again in the background)."""
        pump(lambda: not vt._running())
        dlg.installs = [APT2, FP2]
        dlg.facts["profile"] = FACTS["profile"]
        vt.refresh()
    reset()
    vt.retranslate()
    confirms.clear()
    runs.clear()
    sims.clear()
    before = os.listdir(AUTO_DIR) if os.path.isdir(AUTO_DIR) else []
    vt.btn_update.click()
    check("update: the simulation was asked for the same steps that are shown", sims and sims[-1][0]["sh"].count("apt-get install -y --only-upgrade") == 1, sims)
    check("update: the simulation text is in the first question", confirms and "download 1.6 MiB" in confirms[0] and "go back to an older version" in confirms[0], confirms)
    check("update: a profile copy is made first, then the steps run", pump(lambda: bool(runs)), (runs, vt.log.toPlainText()))
    pump(lambda: not vt._running())
    autos = [n for n in os.listdir(AUTO_DIR) if n.startswith("qgis-profile-auto-")] if os.path.isdir(AUTO_DIR) else []
    check("update: exactly one new automatic copy exists, and it holds the settings but not the cache",
          len(autos) == len(before) + 1 and any("QGIS3.ini" in n for n in zf_mod.ZipFile(os.path.join(AUTO_DIR, sorted(autos)[-1])).namelist())
          and not any("cache" in n for n in zf_mod.ZipFile(os.path.join(AUTO_DIR, sorted(autos)[-1])).namelist()), autos)
    check("update: the log shows the copy before the run", vt.log.toPlainText().index("Copy ready") < vt.log.toPlainText().index("Finished"), vt.log.toPlainText())
    check("the copies list shows it as automatic", vt.backup_table.rowCount() >= 1 and vt.backup_table.item(0, 3).text() == "automatic", vt.backup_table.rowCount())

    # unticked: no copy
    reset()
    vt.chk_auto.setChecked(False)
    n_before = len(os.listdir(AUTO_DIR))
    confirms.clear()
    runs.clear()
    vt.btn_update.click()
    pump(lambda: bool(runs))
    pump(lambda: not vt._running())
    check("with the box unticked no copy is made", len(os.listdir(AUTO_DIR)) == n_before and bool(runs), (n_before, os.listdir(AUTO_DIR)))
    vt.chk_auto.setChecked(True)

    # a copy that cannot be made stops everything
    reset()
    dlg.facts["profile"] = os.path.join(tmp, "no-such-profile")
    confirms.clear()
    runs.clear()
    vt.log.clear()
    vt.btn_update.click()
    pump(lambda: "nothing was changed" in vt.log.toPlainText(), 5)
    check("if the profile cannot be copied, nothing is changed", not runs and "nothing was changed" in vt.log.toPlainText(), (runs, vt.log.toPlainText()))
    dlg.facts["profile"] = FACTS["profile"]

    # side by side: no copy needed
    reset()
    vt.goal_btns["alongside"].setChecked(True)
    n_before = len(os.listdir(AUTO_DIR))
    confirms.clear()
    runs.clear()
    vt.btn_install.click()
    pump(lambda: bool(runs))
    pump(lambda: not vt._running())
    check("a Flatpak install next to QGIS makes no profile copy", len(os.listdir(AUTO_DIR)) == n_before and bool(runs), os.listdir(AUTO_DIR))
    vt.goal_btns["stable"].setChecked(True)

    # other versions
    MAD = ("qgis | 1:3.44.5+24noble | http://qgis.org/ubuntu-ltr noble/main amd64 Packages\n"
           "qgis | 1:3.44.3+24noble | http://qgis.org/ubuntu-ltr noble/main amd64 Packages\n"
           "python3-qgis | 1:3.44.5+24noble | x\npython3-qgis | 1:3.44.3+24noble | x\n")
    real_run = core_versions._run
    core_versions._run = lambda cmd, timeout=120: (0, MAD) if cmd[:2] == ["apt-cache", "madison"] else (1, "")
    try:
        reset()
        tbl.selectRow(0)
        offered = []
        vt._pick_version = lambda rows: offered.append([r["version"] for r in rows]) or rows[1]
        confirms.clear()
        runs.clear()
        n_before = len(os.listdir(AUTO_DIR))
        vt.btn_version.click()
        check("other version: the repositories' versions are offered, the installed one marked",
              pump(lambda: bool(offered)) and offered[0] == ["1:3.44.5+24noble", "1:3.44.3+24noble"], offered)
        check("other version: the commands pin both packages and allow the downgrade",
              pump(lambda: bool(confirms)) and "--allow-downgrades" in confirms[0] and "python3-qgis=1:3.44.3+24noble" in confirms[0]
              and "qgis=1:3.44.3+24noble" in confirms[0], confirms)
        check("other version: it is an in-place change, so a profile copy is made and the steps run",
              pump(lambda: bool(runs)) and len(confirms) == 2 and len(os.listdir(AUTO_DIR)) == n_before + 1, (len(confirms), os.listdir(AUTO_DIR)))
        pump(lambda: not vt._running())
        reset()
        tbl.selectRow(0)
        vt._pick_version = lambda rows: rows[0]                     # the installed version itself
        runs.clear()
        vt.log.clear()
        vt.btn_version.click()
        check("choosing the installed version changes nothing and says so", pump(lambda: "already installed" in vt.log.toPlainText()) and not runs, vt.log.toPlainText())
        core_versions._run = lambda cmd, timeout=120: (1, "")
        reset()
        tbl.selectRow(0)
        vt.log.clear()
        vt.btn_version.click()
        check("no versions on offer: said, nothing run", pump(lambda: "No other versions" in vt.log.toPlainText()), vt.log.toPlainText())
        tbl.clearSelection()
        tbl.setCurrentCell(-1, -1)
        vt.log.clear()
        vt.btn_version.click()
        check("no row selected: a hint", "Pick an installed QGIS" in vt.log.toPlainText(), vt.log.toPlainText())

        # keeping a version
        reset()
        tbl.selectRow(0)
        core_versions._run = lambda cmd, timeout=120: (0, "qgis\n") if cmd[:2] == ["apt-mark", "showhold"] else (1, "")
        vt._check_fn = lambda items: {"updates": [], "locks": {"apt": True, "flatpak-user-stable": None}}
        vt.btn_check.click()
        check("the check also reads which versions are kept", pump(lambda: cell(0, 4) != ""), [cell(r, 4) for r in range(tbl.rowCount())])
        check("kept / not known are told apart", cell(0, 4) == "version kept (not updated)" and cell(1, 4) == "not known", [cell(r, 4) for r in range(2)])
        pump(lambda: not (vt._updates_worker and vt._updates_worker.isRunning()))
        confirms.clear()
        runs.clear()
        n_before = len(os.listdir(AUTO_DIR))
        tbl.selectRow(0)
        core_versions._run = lambda cmd, timeout=120: (0, "") if cmd[:2] == ["apt-mark", "showhold"] else (1, "")   # after releasing: nothing held
        vt.btn_keep.click()
        check("a kept version is released with unhold, with no second question and no copy",
              pump(lambda: bool(runs)) and "apt-mark unhold python3-qgis qgis" in confirms[0] and len(confirms) == 1
              and len(os.listdir(AUTO_DIR)) == n_before, (confirms, runs))
        pump(lambda: not vt._running())
        reset()                                                       # the finished run refreshed the window; the installations come back
        check("afterwards the column is re-read", cell(0, 4) == "updates allowed", cell(0, 4))
        confirms.clear()
        runs.clear()
        reset()
        vt.locks["apt"] = False
        vt._fill_instances()
        tbl.selectRow(0)
        vt.btn_keep.click()
        check("a free version is kept with hold", pump(lambda: bool(runs)) and "apt-mark hold python3-qgis qgis" in confirms[0], confirms)
        pump(lambda: not vt._running())
    finally:
        core_versions._run = real_run
        vt._pick_version = None
        del vt.instance_rows

    # restoring a copy: as a NEW profile, the current one untouched
    pump(lambda: not vt._running())
    vt.refresh()
    tbl_b = vt.backup_table
    check("the copies are listed newest first", tbl_b.rowCount() >= 2 and tbl_b.item(0, 0).text() >= tbl_b.item(1, 0).text(), [tbl_b.item(i, 0).text() for i in range(tbl_b.rowCount())])
    cur_ini = os.path.join(FACTS["profile"], "QGIS", "QGIS3.ini")
    with open(cur_ini, "rb") as fh:
        ini_before = fh.read()
    confirms.clear()
    vt.log.clear()
    tbl_b.clearSelection()
    tbl_b.setCurrentCell(-1, -1)
    vt.btn_restore.click()
    check("restore without a selection: a hint", "Pick a copy" in vt.log.toPlainText(), vt.log.toPlainText())
    tbl_b.selectRow(0)
    vt.btn_restore.click()
    root_dir = os.path.dirname(FACTS["profile"])
    new_dirs = [d for d in os.listdir(root_dir) if d.startswith("restored-")]
    check("restore asks first, naming the new profile and where to pick it in QGIS",
          confirms and "new profile 'restored-" in confirms[0] and "Settings > User Profiles" in confirms[0], confirms)
    check("restore makes a new profile folder next to the current one", len(new_dirs) == 1 and os.path.exists(os.path.join(root_dir, new_dirs[0], "QGIS", "QGIS3.ini")), new_dirs)
    check("the restored profile has no cache and the current profile is untouched",
          not os.path.exists(os.path.join(root_dir, new_dirs[0], "cache")) and open(cur_ini, "rb").read() == ini_before, new_dirs)
    check("the log says where to pick it", "Restored: profile 'restored-" in vt.log.toPlainText() and "User Profiles" in vt.log.toPlainText(), vt.log.toPlainText())
    vt.log.clear()
    vt.btn_restore.click()
    check("restoring the same copy again is refused, never overwritten", "already exists" in vt.log.toPlainText(), vt.log.toPlainText())
    dlg.facts["profile"] = os.path.join(tmp, "odd-place", "x")
    vt.log.clear()
    vt.btn_restore.click()
    check("without a profiles folder to put it in nothing is written", "profiles folder" in vt.log.toPlainText(), vt.log.toPlainText())
    dlg.facts["profile"] = FACTS["profile"]
    dlg.btn_lang.click()
    check("Georgian texts of the copies and the kept column", vt.btn_restore.text().startswith("არჩეულის აღდგენა")
          and vt.backup_table.horizontalHeaderItem(0).text() == "ფაილი" and tbl.horizontalHeaderItem(4).text() == "შენარჩუნება", vt.btn_restore.text())
    dlg.btn_lang.click()

    # the simulation in the background (the default): a dialog without a stub
    d7 = EnvDialog(utils.iface, confirm=lambda title, text: confirms.append(text) or True, facts_fn=lambda: dict(FACTS), dirs_fn=lambda: [plugins],
                   sysinfo={"pm": "apt-get"}, load_installs=False)
    d7.lang = "en"
    confirms.clear()
    seen = []
    d7.confirm_steps("t", "COMMANDS", [{"root": True, "sh": "set -eu\napt-get install -y something-not-here\n"}], lambda: seen.append(1))
    check("simulation in the background: the question comes when it is done", pump(lambda: bool(seen)) and confirms, confirms)
    check("a simulation that could not be made is said so and does not stop the question",
          "COMMANDS" in confirms[0] and "could not be simulated" in confirms[0], confirms)
    d7.close()

    # ---- Components tab ------------------------------------------------------------------
    cp = dlg.components
    cp._info = UBUNTU
    dlg.facts = dict(FACTS)
    missing.clear()
    missing.update({"gdal", "numpy", "scipy", "windninja"})         # what the stub says is not installed
    dlg.retranslate()
    check("components tab is the fourth tab", dlg.tabs.tabText(3) == "Components", dlg.tabs.tabText(3))
    tops = [cp.tree.topLevelItem(i).text(0) for i in range(cp.tree.topLevelItemCount())]
    check("four groups in the order of the OSGeo4W-like chooser", tops == ["Command line tools", "GIS engines", "Python libraries", "Database clients"], tops)

    def comp_item(rid):
        for i in range(cp.tree.topLevelItemCount()):
            top = cp.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, cp_role) == rid:
                    return top.child(j)

    from qgis_environment_manager.components_tab import ROLE_ID as cp_role
    from qgis.PyQt.QtCore import Qt as QtCore_Qt
    gd, npy, pj, wn = comp_item("gdal"), comp_item("numpy"), comp_item("proj"), comp_item("windninja")
    check("a missing component with a package can be ticked and shows its package",
          bool(gd.flags() & QtCore_Qt.ItemFlag.ItemIsUserCheckable) and "[missing]" in gd.text(0) and "gdal-bin" in gd.text(0), gd.text(0))
    check("an installed component cannot be ticked", "[installed]" in pj.text(0) and not (pj.flags() & QtCore_Qt.ItemFlag.ItemIsUserCheckable), pj.text(0))
    check("a component without a package says so and cannot be ticked", "no package" in wn.text(0) and not (wn.flags() & QtCore_Qt.ItemFlag.ItemIsUserCheckable), wn.text(0))
    check("nothing ticked: install disabled, hint shown", not cp.btn_install.isEnabled() and "Tick the components" in cp.note.text(), cp.note.text())
    gd.setCheckState(0, QtCore_Qt.CheckState.Checked)
    npy.setCheckState(0, QtCore_Qt.CheckState.Checked)
    check("two ticked: counted, install enabled", cp.selected() == ["gdal", "numpy"] and cp.btn_install.isEnabled() and "Selected: 2" in cp.note.text(), (cp.selected(), cp.note.text()))
    confirms.clear()
    runs.clear()
    cp.btn_install.click()
    check("the reviewed commands name exactly the ticked packages", confirms and "apt-get install -y gdal-bin python3-numpy" in confirms[0]
          and "scipy" not in confirms[0], confirms)
    check("the steps ran as root through the elevator", pump(lambda: bool(runs)) and runs[0][0][0]["root"] is True, runs)
    check("the log says it finished", pump(lambda: "Finished" in cp.log.toPlainText()), cp.log.toPlainText())
    pump(lambda: not cp._running())
    check("afterwards the list is refreshed: nothing left to tick",
          cp.selected() == [] and "[installed]" in comp_item("gdal").text(0), comp_item("gdal").text(0))
    for label, facts, needle in (("flatpak QGIS", dict(FACTS, runtime="flatpak"), "sandboxed (flatpak)"),
                                 ("not Linux", dict(FACTS, is_linux=False), "only works on Linux")):
        d6 = EnvDialog(utils.iface, facts_fn=lambda f=facts: dict(f), dirs_fn=lambda: [plugins], sysinfo={"pm": "apt-get"}, load_installs=False)
        d6.lang = "en"
        d6.components._info = UBUNTU
        d6.retranslate()
        gd6 = None
        for i in range(d6.components.tree.topLevelItemCount()):
            top = d6.components.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, cp_role) == "gdal":
                    gd6 = top.child(j)
        check("components blocked: " + label, needle in d6.components.blocker.text() and not d6.components.btn_install.isEnabled()
              and gd6 is not None and not (gd6.flags() & QtCore_Qt.ItemFlag.ItemIsUserCheckable), d6.components.blocker.text())
        d6.close()
    dlg.btn_lang.click()
    check("Georgian title and texts of the components tab", dlg.tabs.tabText(3) == "კომპონენტები"
          and "ბრძანების სტრიქონის" in cp.tree.topLevelItem(0).text(0), (dlg.tabs.tabText(3), cp.tree.topLevelItem(0).text(0)))
    dlg.btn_lang.click()

    # ---- the environment file (Components tab) ----------------------------------------------
    from qgis_environment_manager.qgis_installer import envspec as core_envspec
    cp._info = UBUNTU
    dlg.facts = dict(FACTS)
    dlg.installs = [{"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "1:3.44.5+24noble", "o": "qgis.org", "root": True}]
    missing.clear()
    missing.update({"gdal", "numpy"})
    cp.refresh()
    env_dir = os.path.join(tmp, "envfiles")
    os.makedirs(env_dir, exist_ok=True)

    def write_env(name, doc):
        path = os.path.join(env_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc if isinstance(doc, str) else json.dumps(doc))
        return path

    check("the environment file group is there, with three buttons", cp.btn_env_save.text().startswith("Save this machine") and cp.btn_env_check.isEnabled(),
          cp.btn_env_save.text())
    saved = os.path.join(env_dir, "saved.json")
    cp._pick_save = lambda: saved
    cp.log.clear()
    cp.btn_env_save.click()
    spec_saved = json.load(open(saved, encoding="utf-8")) if os.path.exists(saved) else {}
    check("saving writes a valid environment file with the components that are there and the QGIS that is installed",
          core_envspec.validate(spec_saved) and "proj" in spec_saved["components"] and "gdal" not in spec_saved["components"]
          and spec_saved["qgis"]["recipe"] == "apt-distro", spec_saved)
    check("the log says where it was saved", "Saved: " in cp.log.toPlainText() and saved in cp.log.toPlainText(), cp.log.toPlainText())
    dlg.installs = None
    cp.log.clear()
    cp.btn_env_save.click()
    check("while the installations are still being looked for it does not write a file that lacks QGIS", "Checking" in cp.log.toPlainText(), cp.log.toPlainText())
    dlg.installs = [{"kind": "apt", "pkgs": ["python3-qgis", "qgis"], "v": "1:3.44.5+24noble", "o": "qgis.org", "root": True}]

    wanted = write_env("want.json", {"schema": 1, "name": "lab", "components": ["gdal", "numpy", "proj"],
                                     "qgis": {"goal": "stable", "recipe": "apt-official", "options": {"channel": "ltr"}, "version": "3.44.5"}})
    cp._pick_open = lambda: wanted
    cp.log.clear()
    cp.btn_env_check.click()
    text = cp.log.toPlainText()
    check("comparing says what is there and what is missing, and changes nothing",
          "QGIS: installed (1:3.44.5+24noble), as the file asks" in text and "Components: 1 of 3 present" in text
          and "to install: GDAL command line tools" in text and not runs[-1:] == [None], text)

    confirms.clear()
    runs.clear()
    sims.clear()
    cp.log.clear()
    cp.btn_env_apply.click()
    check("applying shows the file's state, the commands for exactly what is missing and the simulation first",
          confirms and "apt-get install -y gdal-bin python3-numpy" in confirms[0] and "Components: 1 of 3 present" in confirms[0]
          and "What the package manager says" in confirms[0] and "proj-bin" not in confirms[0], confirms)
    check("then it runs them as root through the elevator", pump(lambda: bool(runs)) and runs[0][0][0]["root"] is True, runs)
    pump(lambda: not cp._running())
    check("afterwards the list is refreshed and the same file now matches", all(
        "[installed]" in comp_item(c).text(0) for c in ("gdal", "numpy")), [comp_item(c).text(0) for c in ("gdal", "numpy")])
    cp.log.clear()
    confirms.clear()
    runs.clear()
    cp.btn_env_apply.click()
    check("applying it again says it already matches and asks nothing", "already matches" in cp.log.toPlainText() and not confirms and not runs, cp.log.toPlainText())

    for label, doc, needle in (("recipe", {"schema": 1, "components": [], "qgis": {"goal": "stable", "recipe": "x; rm -rf ~", "options": {}}}, "unknown recipe"),
                               ("component", {"schema": 1, "components": ["gdal", "evil"]}, "unknown component"),
                               ("json", "{nope", "Not a valid environment file"),
                               ("big", " " * (70 * 1024), "larger than 64 KB")):
        cp._pick_open = lambda path=write_env("bad_" + label + ".json", doc): path
        confirms.clear()
        runs.clear()
        cp.log.clear()
        cp.btn_env_apply.click()
        check("a bad file is refused with the reason, nothing asked or run: " + label,
              needle in cp.log.toPlainText() and not confirms and not runs, (cp.log.toPlainText(), confirms, runs))
    cp._pick_open = lambda: os.path.join(env_dir, "nope.json")
    cp.log.clear()
    cp.btn_env_apply.click()
    check("a file that is not there is said so", "Could not work with the file" in cp.log.toPlainText(), cp.log.toPlainText())

    for label, facts, needle in (("flatpak QGIS", dict(FACTS, runtime="flatpak"), "sandboxed (flatpak)"), ("not Linux", dict(FACTS, is_linux=False), "only works on Linux")):
        d8 = EnvDialog(utils.iface, facts_fn=lambda f=facts: dict(f), dirs_fn=lambda: [plugins], sysinfo={"pm": "apt-get"}, load_installs=False)
        d8.lang = "en"
        d8.components._info = UBUNTU
        d8.retranslate()
        check("environment file apply is blocked: " + label, not d8.components.btn_env_apply.isEnabled() and needle in d8.components.blocker.text(),
              d8.components.blocker.text())
        d8.close()
    dlg.btn_lang.click()
    check("Georgian texts of the environment file group", cp.g_env.title() == "გარემოს ფაილი" and cp.btn_env_apply.text().endswith("მისადაგება…"), cp.g_env.title())
    dlg.btn_lang.click()
    missing.clear()

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
