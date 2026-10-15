# -*- coding: utf-8 -*-
"""The "QGIS versions" tab: update what is installed, install another QGIS next to it or in its place, back up the profile.

Everything it would run is shown first (commands, instructions, warnings) and runs only after confirmation. Recipes that live
apart from the system's QGIS (Flatpak, containers, Spack) can be installed while QGIS is running; the others change the QGIS
that is running right now, so they need a second, explicit confirmation. Inside a sandboxed QGIS (Flatpak, Snap) or off
Linux nothing is run at all - the tab says why.
"""
from __future__ import annotations

import os

from qgis.PyQt.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from . import profile_backup
from .qgis_installer import i18n as core_i18n
from .qgis_installer import recipes, runner, system, update
from .workers import StepsWorker


def plan_text(result: dict, lang: str) -> str:
    """Steps, manual instructions and warnings of a plan as one text: what the user reads before agreeing."""
    t = lambda k, **kw: core_i18n.t(k, lang, **kw)  # noqa: E731
    parts = []
    if result["steps"]:
        parts.append(core_i18n.steps_text(result["steps"], lang))
    for m in result["manual"]:
        parts.append("# " + t("rcm_" + m["title"]) + "\n" + m["text"])
    parts.extend("* " + t("rcw_" + k) for k in result["notes"])
    return "\n\n".join(parts)


def human_size(n: int) -> str:
    return "{:.0f} MB".format(n / 1048576) if n >= 1048576 else "{:.0f} KB".format(max(n, 1) / 1024)


class VersionsTab(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.d = dialog
        self.recipe_ids: list = []
        self.rec: dict = {}
        self.rec_options: dict = {}
        self.chan_keys: list = []
        self.worker = None
        self._steps: list = []
        self._pick_dir = None                     # tests inject a folder chooser
        self._info = None                         # tests inject a system description
        self._build()

    # ---- UI ----------------------------------------------------------------------
    def _build(self):
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setWordWrap(True)
        self.blocker = QLabel()
        self.blocker.setWordWrap(True)
        self.blocker.setStyleSheet("color:#b42318")
        lay.addWidget(self.head)
        lay.addWidget(self.blocker)

        self.g_update = QGroupBox()
        v = QVBoxLayout(self.g_update)
        self.lbl_update = QLabel()
        self.lbl_update.setWordWrap(True)
        self.btn_update = QPushButton()
        v.addWidget(self.lbl_update)
        v.addWidget(self.btn_update)
        lay.addWidget(self.g_update)

        self.g_other = QGroupBox()
        v = QVBoxLayout(self.g_other)
        self.goal_btns = {}
        for goal in recipes.GOALS:
            b = QRadioButton()
            b.toggled.connect(lambda on, g=goal: on and self._on_goal(g))
            self.goal_btns[goal] = b
            v.addWidget(b)
        self.goal_btns["stable"].setChecked(True)
        self.lbl_rec = QLabel()
        self.lbl_rec.setWordWrap(True)
        self.lbl_rec.setStyleSheet("color:#1d4ed8")
        self.cmb_recipe = QComboBox()
        self.lbl_where = QLabel()
        self.lbl_where.setWordWrap(True)
        v.addWidget(self.lbl_rec)
        v.addWidget(self.cmb_recipe)
        v.addWidget(self.lbl_where)
        self.opt_label, self.opt_cmb = {}, {}
        for name in ("channel", "branch", "scope"):
            self.opt_label[name], self.opt_cmb[name] = QLabel(), QComboBox()
            v.addWidget(self.opt_label[name])
            v.addWidget(self.opt_cmb[name])
        self.btn_install = QPushButton()
        v.addWidget(self.btn_install)
        lay.addWidget(self.g_other)

        self.g_backup = QGroupBox()
        v = QVBoxLayout(self.g_backup)
        self.lbl_backup = QLabel()
        self.lbl_backup.setWordWrap(True)
        self.btn_backup = QPushButton()
        v.addWidget(self.lbl_backup)
        v.addWidget(self.btn_backup)
        lay.addWidget(self.g_backup)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.log, 1)

        self.cmb_recipe.currentIndexChanged.connect(self._on_recipe)
        self.opt_cmb["channel"].currentIndexChanged.connect(lambda *_: None)
        self.btn_update.clicked.connect(self.run_update)
        self.btn_install.clicked.connect(self.run_install)
        self.btn_backup.clicked.connect(self.run_backup)

    def tr_(self, key, **kw):
        return self.d.tr_(key, **kw)

    def core(self, key, **kw):
        return core_i18n.t(key, self.d.lang, **kw)

    def retranslate(self):
        self.head.setText(self.tr_("vt_head"))
        self.g_update.setTitle(self.tr_("vt_update_h"))
        self.btn_update.setText(self.tr_("vt_update_btn"))
        self.g_other.setTitle(self.tr_("vt_other_h"))
        for goal, b in self.goal_btns.items():
            b.setText(self.core("goal_" + goal))
        for name, key in (("channel", "o_channel"), ("branch", "o_branch"), ("scope", "o_scope")):
            self.opt_label[name].setText(self.core(key))
        self.btn_install.setText(self.tr_("vt_install_btn"))
        self.g_backup.setTitle(self.tr_("vt_backup_h"))
        self.lbl_backup.setText(self.tr_("vt_backup_text"))
        self.btn_backup.setText(self.tr_("vt_backup_btn"))
        self._on_goal(self.goal())
        self.refresh()

    # ---- state -------------------------------------------------------------------
    def sysinfo(self):
        return self._info or system.detect()

    def blocked(self):
        """Why nothing can be run from here (text), or None."""
        f = self.d.facts
        if not f.get("is_linux"):
            return self.tr_("rq_no_linux")
        if f.get("runtime") != "native":
            return self.tr_("rq_sandbox", kind=f.get("runtime"))
        return None

    def refresh(self):
        reason = self.blocked()
        self.blocker.setText(reason or "")
        self.blocker.setVisible(bool(reason))
        items = self.d.installs
        plan = update.plan(items or [], self.sysinfo())
        if items is None:
            self.lbl_update.setText(self.tr_("installs_loading"))
        elif plan["steps"] or plan["manual"]:
            self.lbl_update.setText(self.tr_("vt_update_found", n=len([i for i in items if i["kind"] not in ("repo", "data")])))
        else:
            self.lbl_update.setText(self.tr_("vt_update_none"))
        self.btn_update.setEnabled(reason is None and bool(plan["steps"] or plan["manual"]) and not self._running())
        self.btn_install.setEnabled(self.recipe_id() is not None and reason is None and not self._running())
        self.btn_backup.setEnabled(not self._running())

    def goal(self):
        return next(g for g, b in self.goal_btns.items() if b.isChecked())

    def _running(self):
        return bool(self.worker and self.worker.isRunning())

    def _on_goal(self, goal):
        info = self.sysinfo()
        self.rec = recipes.recommend(info, goal)
        self.rec_options = dict(self.rec["options"])
        if self.rec["recipe"] is None:
            self.lbl_rec.setText(self.core("why_nothing_fits", url=recipes.GUIDE_URL))
        else:
            self.lbl_rec.setText(self.core("recommended", name=self.core("rc_" + self.rec["recipe"])) + " " +
                                 self.core("why_" + self.rec["why"], url=recipes.GUIDE_URL))
        self._fill_recipes(self.rec["recipe"])

    def _fill_recipes(self, select=None):
        info = self.sysinfo()
        rows = [a for a in recipes.available(info) if a["applies"]]
        self.recipe_ids = [a["id"] for a in rows]
        self.cmb_recipe.blockSignals(True)
        self.cmb_recipe.clear()
        for a in rows:
            self.cmb_recipe.addItem(self.core("rc_" + a["id"]))
        if select in self.recipe_ids:
            self.cmb_recipe.setCurrentIndex(self.recipe_ids.index(select))
        self.cmb_recipe.blockSignals(False)
        self._on_recipe()

    def recipe_id(self):
        i = self.cmb_recipe.currentIndex()
        return self.recipe_ids[i] if 0 <= i < len(self.recipe_ids) else None

    def _on_recipe(self, *_):
        rid = self.recipe_id()
        for name in self.opt_cmb:
            self.opt_label[name].setVisible(False)
            self.opt_cmb[name].setVisible(False)
        self.btn_install.setEnabled(rid is not None and self.blocked() is None and not self._running())
        if rid is None:
            self.lbl_where.setText("")
            return
        r = recipes.RECIPES[rid]
        self.lbl_where.setText(self.tr_("vt_side_yes" if r["side_by_side"] else "vt_side_no") + "  " + self.core("vf_" + r["verified"]))
        want = r["options"]

        def show(name, keys, label, current=None):
            self.opt_label[name].setVisible(True)
            self.opt_cmb[name].setVisible(True)
            self.opt_cmb[name].clear()
            for k in keys:
                self.opt_cmb[name].addItem(label(k))
            if current in keys:
                self.opt_cmb[name].setCurrentIndex(keys.index(current))
            return keys

        if "channel" in want:
            if rid == "apt-official":
                self.chan_keys = list(system.allowed_channels(self.sysinfo()))
                label = lambda k: self.core("ch_" + k, v=system.LATEST if k == "latest" else system.LTR)  # noqa: E731
            elif rid == "aur-helper":
                self.chan_keys, label = list(recipes.AUR_CHANNELS), lambda k: self.core("aur_" + k)  # noqa: E731
            else:
                self.chan_keys, label = ["latest", "ltr"], lambda k: self.core("nixch_" + k)  # noqa: E731
            show("channel", self.chan_keys, label, self.rec_options.get("channel") or ("ltr" if "ltr" in self.chan_keys else None))
        if "branch" in want:
            show("branch", list(recipes.FLATPAK_BRANCHES), lambda k: self.core("br_" + k), self.rec_options.get("branch", "stable"))
        if "scope" in want:
            show("scope", ["user", "system"], lambda k: self.core("sc_" + k), "user")

    def options(self, rid):
        want = recipes.RECIPES[rid]["options"]
        o = {}
        if "channel" in want:
            o["channel"] = self.chan_keys[self.opt_cmb["channel"].currentIndex()]
        if "branch" in want:
            o["branch"] = recipes.FLATPAK_BRANCHES[self.opt_cmb["branch"].currentIndex()]
        if "scope" in want:
            o["scope"] = ("user", "system")[self.opt_cmb["scope"].currentIndex()]
        return o

    # ---- actions -----------------------------------------------------------------
    def run_update(self):
        result = update.plan(self.d.installs or [], self.sysinfo())
        self._confirm_and_run(result, in_place=True, title_key="vt_update_h")

    def run_install(self):
        rid = self.recipe_id()
        if rid is None:
            return
        result = recipes.make_plan(rid, self.sysinfo(), self.options(rid))
        self._confirm_and_run(result, in_place=not recipes.RECIPES[rid]["side_by_side"], title_key="vt_other_h")

    def _confirm_and_run(self, result, in_place, title_key):
        if self.blocked() is not None or self._running():
            return
        text = plan_text(result, self.d.lang)
        if not result["steps"]:                    # instructions only: show them, nothing to run
            self.d._confirm(self.tr_(title_key), self.tr_("vt_manual_only", text=text))
            return
        if not self.d._confirm(self.tr_("rq_confirm_title"), self.tr_("rq_confirm", text=text)):
            return
        if in_place and not self.d._confirm(self.tr_("vt_inplace_title"), self.tr_("vt_inplace_confirm")):
            return
        self.log.clear()
        self.log.appendPlainText(self.tr_("rq_running"))
        self._steps = result["steps"]
        self.worker = StepsWorker(self._steps, runner.default_elevator(), self, self.d._run_steps)
        self.worker.line.connect(self.log.appendPlainText)
        self.worker.done.connect(self._on_done)
        self.btn_update.setEnabled(False)
        self.btn_install.setEnabled(False)
        self.worker.start()

    def _on_done(self, rc, failed):
        if rc == 0:
            self.log.appendPlainText(self.tr_("rq_done"))
        elif runner.needs_elevation_fallback(rc, failed):
            self.log.appendPlainText(self.tr_("rq_elev_fail", cmd="sudo sh " + runner.write_root_script(self._steps)))
        else:
            self.log.appendPlainText(self.tr_("rq_failed", rc=rc))
        self.d.refresh()

    def run_backup(self):
        profile = self.d.facts.get("profile") or ""
        if not profile or not os.path.isdir(profile):
            self.log.appendPlainText(self.tr_("vt_backup_fail", why=profile or "?"))
            return
        count, size = profile_backup.estimate(profile)
        dest = self._pick_dir(profile) if self._pick_dir else QFileDialog.getExistingDirectory(
            self, self.tr_("vt_backup_btn"), os.path.expanduser("~"))
        if not dest:
            return
        try:
            res = profile_backup.backup(profile, dest)
        except (OSError, ValueError) as exc:
            self.log.appendPlainText(self.tr_("vt_backup_fail", why=str(exc)))
            return
        self.log.appendPlainText(self.tr_("vt_backup_done", path=res["path"], files=res["files"], size=human_size(res["bytes"]),
                                          est=human_size(size), n=count))
