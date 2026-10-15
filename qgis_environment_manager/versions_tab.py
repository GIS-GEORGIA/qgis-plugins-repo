# -*- coding: utf-8 -*-
"""The "QGIS versions" tab: update what is installed, install another QGIS next to it or in its place, back up the profile.

Everything it would run is shown first (commands, instructions, warnings) and runs only after confirmation. Recipes that live
apart from the system's QGIS (Flatpak, containers, Spack) can be installed while QGIS is running; the others change the QGIS
that is running right now, so they need a second, explicit confirmation. Inside a sandboxed QGIS (Flatpak, Snap) or off
Linux nothing is run at all - the tab says why.
"""
from __future__ import annotations

import datetime
import os

from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QPlainTextEdit,
    QPushButton, QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import profile_backup
from .qgis_installer import i18n as core_i18n
from .qgis_installer import instances, recipes, runner, system, update, versions
from .workers import FuncWorker, StepsWorker, UpdatesWorker


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


def check_all(items):
    """What the "Check" button asks: is a newer build waiting, and is the installed version kept? (both only read)"""
    return {"updates": instances.check_updates(items),
            "locks": {r["id"]: versions.lock_state(r["label_item"]) for r in instances.list_instances(items)}}


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
        self._popen = None                        # tests inject a process starter
        self._check_fn = None                     # tests inject the update check
        self.updates: dict = {}                   # instance id -> check_updates row
        self._updates_worker = None
        self._info = None                         # tests inject a system description
        self._pick_version = None                 # tests inject the chooser of a version: (rows) -> row or None
        self._backup_dir = None                   # tests inject the folder of the automatic copies
        self.locks: dict = {}                     # instance id -> True kept / False free / None not known
        self._func = None
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

        self.g_inst = QGroupBox()
        v = QVBoxLayout(self.g_inst)
        self.inst_table = QTableWidget(0, 5)
        self.inst_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inst_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inst_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.inst_table.verticalHeader().setVisible(False)
        self.inst_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.inst_table.horizontalHeader().setStretchLastSection(True)
        self.inst_table.setMaximumHeight(150)
        self.lbl_check = QLabel()
        self.lbl_check.setWordWrap(True)
        row = QHBoxLayout()
        self.btn_check = QPushButton()
        self.btn_start = QPushButton()
        self.btn_version = QPushButton()
        self.btn_keep = QPushButton()
        row.addWidget(self.btn_check)
        row.addWidget(self.btn_start)
        row.addWidget(self.btn_version)
        row.addWidget(self.btn_keep)
        row.addStretch(1)
        v.addWidget(self.inst_table)
        v.addWidget(self.lbl_check)
        v.addLayout(row)
        lay.addWidget(self.g_inst)

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
        self.chk_auto = QCheckBox()
        self.chk_auto.setChecked(True)
        self.backup_table = QTableWidget(0, 4)
        self.backup_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.backup_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backup_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backup_table.verticalHeader().setVisible(False)
        self.backup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.backup_table.horizontalHeader().setStretchLastSection(True)
        self.backup_table.setMaximumHeight(110)
        self.btn_restore = QPushButton()
        brow = QHBoxLayout()
        brow.addWidget(self.btn_backup)
        brow.addWidget(self.btn_restore)
        brow.addStretch(1)
        v.addWidget(self.lbl_backup)
        v.addWidget(self.chk_auto)
        v.addWidget(self.backup_table)
        v.addLayout(brow)
        lay.addWidget(self.g_backup)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.log, 1)

        self.cmb_recipe.currentIndexChanged.connect(self._on_recipe)
        self.opt_cmb["channel"].currentIndexChanged.connect(lambda *_: None)
        self.btn_check.clicked.connect(self.check_updates)
        self.btn_start.clicked.connect(self.start_selected)
        self.btn_version.clicked.connect(self.choose_version)
        self.btn_keep.clicked.connect(self.toggle_keep)
        self.btn_restore.clicked.connect(self.restore_selected)
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
        self.g_inst.setTitle(self.tr_("vt_inst_h"))
        self.inst_table.setHorizontalHeaderLabels(self.tr_("vt_inst_cols"))
        self.lbl_check.setText(self.tr_("vt_check_note"))
        self.btn_check.setText(self.tr_("vt_check_btn"))
        self.btn_start.setText(self.tr_("vt_start_btn"))
        self.btn_version.setText(self.tr_("vt_other_version_btn"))
        self.btn_keep.setText(self.tr_("vt_keep_btn"))
        self.chk_auto.setText(self.tr_("vt_auto_chk"))
        self.backup_table.setHorizontalHeaderLabels(self.tr_("vt_backup_cols"))
        self.btn_restore.setText(self.tr_("vt_restore_btn"))
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
        self._fill_instances()
        self._fill_backups()

    # ---- installed programs ---------------------------------------------------------
    def instance_rows(self):
        return instances.list_instances(self.d.installs or [])

    def _fill_instances(self):
        rows = self.instance_rows()
        self.inst_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            u = self.updates.get(r["id"])
            if u is None:
                state = ""
            else:
                state = {True: self.core("upd_available"), False: self.core("upd_current"), None: self.core("upd_unknown")}[u["update"]]
                if u["update"] and u.get("candidate"):
                    state += " ({})".format(u["candidate"])
            how = " ".join(r["launch"]) if r["launch"] else self.core("inst_cannot_launch")
            kept = self.locks.get(r["id"], "unchecked")
            kept_text = "" if kept == "unchecked" else {True: self.core("lock_kept"), False: self.core("lock_free"), None: self.core("lock_unknown")}[kept]
            for c, text in enumerate((core_i18n.label_for(r["label_item"], self.d.lang), r["version"], state, how, kept_text)):
                item = QTableWidgetItem(text)
                if c == 2 and u is not None and u["update"]:
                    item.setForeground(QColor("#e65100"))
                if c == 2 and u is not None:
                    item.setToolTip(self.core("upd_" + u["source"]))
                self.inst_table.setItem(i, c, item)
        if self.d.installs is None:
            self.lbl_check.setText(self.tr_("vt_inst_loading"))
        elif not rows:
            self.lbl_check.setText(self.tr_("vt_inst_none"))
        else:
            self.lbl_check.setText(self.tr_("vt_check_note"))
        busy = self._running() or bool(self._updates_worker and self._updates_worker.isRunning())
        self.btn_check.setEnabled(bool(rows) and not busy)
        self.btn_start.setEnabled(any(r["launchable"] for r in rows))
        self.btn_version.setEnabled(bool(rows) and self.blocked() is None and not busy)
        self.btn_keep.setEnabled(bool(rows) and self.blocked() is None and not busy)

    def check_updates(self):
        items = self.d.installs or []
        if not items or (self._updates_worker and self._updates_worker.isRunning()):
            return
        self.btn_check.setEnabled(False)
        self.lbl_check.setText(self.tr_("vt_checking"))
        self._updates_worker = UpdatesWorker(items, self, self._check_fn or check_all)
        self._updates_worker.done.connect(self._on_checked)
        self._updates_worker.start()

    def _on_checked(self, result):
        rows = result["updates"] if isinstance(result, dict) else result          # (a test may hand over just the updates)
        if isinstance(result, dict):
            self.locks.update(result.get("locks", {}))
        self.updates = {r["id"]: r for r in rows}
        self._fill_instances()

    def start_selected(self):
        rows = self.instance_rows()
        sel = self.inst_table.currentRow()
        if not (0 <= sel < len(rows)) or not rows[sel]["launchable"]:
            self.log.appendPlainText(self.tr_("vt_start_none"))
            return
        row = rows[sel]
        note = self.core("inst_profile") if row["shared_profile"] else ""
        if not self.d._confirm(self.tr_("vt_start_title"), self.tr_("vt_start_confirm", cmd=" ".join(row["launch"]), note=note).strip()):
            return
        try:
            pid = instances.launch(row, popen=self._popen)
        except (OSError, ValueError) as exc:
            self.log.appendPlainText(self.tr_("vt_start_fail", why=str(exc)))
            return
        self.log.appendPlainText(self.tr_("vt_started", pid=pid))

    def _selected_instance(self):
        rows = self.instance_rows()
        sel = self.inst_table.currentRow()
        return rows[sel] if 0 <= sel < len(rows) else None

    def choose_version(self):
        row = self._selected_instance()
        if row is None:
            self.log.appendPlainText(self.tr_("vt_pick_row"))
            return
        item = row["label_item"]
        self.log.appendPlainText(self.tr_("vt_ver_looking"))
        self._func = FuncWorker(lambda: versions.available(item), self)
        self._func.done.connect(lambda res: self._on_versions(item, res))
        self._func.start()

    def _on_versions(self, item, found):
        if isinstance(found, Exception) or not found["versions"]:
            self.log.appendPlainText(self.core("ver_none") + ("  " + self.core("rcw_" + found["note"]) if not isinstance(found, Exception) and found.get("note") else ""))
            return
        rows = found["versions"]
        if self._pick_version is not None:
            chosen = self._pick_version(rows)
        else:
            labels = ["{}  [{}] {}".format(r["version"], r["origin"], self.core("ver_installed") if r["installed"] else "").strip() for r in rows]
            text, ok = QInputDialog.getItem(self, self.tr_("vt_ver_pick_title"), self.core("rcw_" + found["note"]) if found.get("note") else "", labels, 0, False)
            chosen = rows[labels.index(text)] if ok else None
        if chosen is None:
            return
        if chosen.get("installed"):
            self.log.appendPlainText(self.tr_("vt_ver_same"))
            return
        try:
            result = versions.steps_for(item, chosen)
        except ValueError as exc:
            self.log.appendPlainText(self.tr_("vt_ver_fail", why=str(exc)))
            return
        result["manual"] = []
        self._confirm_and_run(result, in_place=item["kind"] != "flatpak", title_key="vt_other_version_btn")

    def toggle_keep(self):
        row = self._selected_instance()
        if row is None:
            self.log.appendPlainText(self.tr_("vt_pick_row"))
            return
        item = row["label_item"]
        state = self.locks.get(row["id"], "unchecked")
        if state == "unchecked":
            state = versions.lock_state(item)
        result = versions.lock_steps(item, state is not True)                     # kept now -> release; free or not known -> keep
        result["notes"] = list(result["notes"])
        self._pending_lock = row["id"]
        self._confirm_and_run(result, in_place=False, title_key="vt_keep_btn", after=self._after_keep)

    def _after_keep(self):
        rid = getattr(self, "_pending_lock", None)
        row = next((r for r in self.instance_rows() if r["id"] == rid), None)
        if row is not None:
            self.locks[rid] = versions.lock_state(row["label_item"])
            self._fill_instances()

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

    def _confirm_and_run(self, result, in_place, title_key, after=None):
        if self.blocked() is not None or self._running():
            return
        text = plan_text(result, self.d.lang)
        if not result["steps"]:                    # instructions only: show them, nothing to run
            self.d._confirm(self.tr_(title_key), self.tr_("vt_manual_only", text=text))
            return

        def confirmed():
            if in_place and not self.d._confirm(self.tr_("vt_inplace_title"), self.tr_("vt_inplace_confirm")):
                return
            self.log.clear()
            if in_place and self.chk_auto.isChecked():
                self._auto_backup(lambda: self._run(result["steps"], after))
            else:
                self._run(result["steps"], after)
        self.d.confirm_steps(self.tr_("rq_confirm_title"), text, result["steps"], confirmed, log=self.log)

    def _auto_backup(self, then):
        """The profile is copied before QGIS itself is changed. If the copy cannot be made nothing is changed: it is the safer way round."""
        profile = self.d.facts.get("profile") or ""
        dest = self._backup_dir or profile_backup.default_dir()
        if not profile or not os.path.isdir(profile):
            self.log.appendPlainText(self.tr_("vt_backup_auto_fail", why=profile or "?"))
            return
        self.log.appendPlainText(self.tr_("vt_backup_auto_start"))
        self._func = FuncWorker(lambda: profile_backup.backup(profile, dest, profile_backup.auto_name(), unique=True), self)

        def done(res):
            if isinstance(res, Exception):
                self.log.appendPlainText(self.tr_("vt_backup_auto_fail", why=str(res)))
                return
            self.log.appendPlainText(self.tr_("vt_backup_done", path=res["path"], files=res["files"], size=human_size(res["bytes"]), est="", n=""))
            profile_backup.prune_auto(dest)
            self._fill_backups()
            then()
        self._func.done.connect(done)
        self._func.start()

    def _run(self, steps, after=None):
        self.log.appendPlainText(self.tr_("rq_running"))
        self._steps = steps
        self._after = after
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
        after, self._after = getattr(self, "_after", None), None
        if after is not None and rc == 0:
            after()
        self.d.refresh()

    def run_backup(self):
        profile = self.d.facts.get("profile") or ""
        if not profile or not os.path.isdir(profile):
            self.log.appendPlainText(self.tr_("vt_backup_fail", why=profile or "?"))
            return
        count, size = profile_backup.estimate(profile)
        dest = self._pick_dir(profile) if self._pick_dir else QFileDialog.getExistingDirectory(
            self, self.tr_("vt_backup_btn"), profile_backup.default_dir() if os.path.isdir(profile_backup.default_dir()) else os.path.expanduser("~"))
        if not dest:
            return
        try:
            res = profile_backup.backup(profile, dest)
        except (OSError, ValueError) as exc:
            self.log.appendPlainText(self.tr_("vt_backup_fail", why=str(exc)))
            return
        self.log.appendPlainText(self.tr_("vt_backup_done", path=res["path"], files=res["files"], size=human_size(res["bytes"]),
                                          est=human_size(size), n=count))
        self._fill_backups()

    # ---- the copies and getting one back ------------------------------------------------
    def backup_dir(self):
        return self._backup_dir or profile_backup.default_dir()

    def _fill_backups(self):
        rows = profile_backup.list_backups(self.backup_dir())
        self.backup_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            when = datetime.datetime.fromtimestamp(r["mtime"]).strftime("%Y-%m-%d %H:%M")
            kind = self.tr_("vt_backup_auto") if r["auto"] else self.tr_("vt_backup_manual")
            for c, text in enumerate((r["name"], human_size(r["bytes"]), when, kind)):
                self.backup_table.setItem(i, c, QTableWidgetItem(text))
        self.btn_restore.setEnabled(bool(rows))

    def restore_selected(self):
        rows = profile_backup.list_backups(self.backup_dir())
        sel = self.backup_table.currentRow()
        if not (0 <= sel < len(rows)):
            self.log.appendPlainText(self.tr_("vt_restore_none"))
            return
        profile = self.d.facts.get("profile") or ""
        root = os.path.dirname(profile.rstrip("/\\"))
        if not profile or os.path.basename(root) != "profiles":
            self.log.appendPlainText(self.tr_("vt_restore_fail", why=self.tr_("vt_restore_no_root", path=profile or "?")))
            return
        name = os.path.splitext(rows[sel]["name"])[0].replace("qgis-profile-", "restored-")
        if not self.d._confirm(self.tr_("vt_restore_btn"), self.tr_("vt_restore_confirm", name=name, root=root)):
            return
        try:
            res = profile_backup.restore_as_new_profile(rows[sel]["path"], root, name)
        except (OSError, ValueError) as exc:
            self.log.appendPlainText(self.tr_("vt_restore_fail", why=str(exc)))
            return
        self.log.appendPlainText(self.tr_("vt_restore_done", name=res["name"], files=res["files"], path=res["path"]))
