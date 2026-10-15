# -*- coding: utf-8 -*-
"""The QGIS Environment Manager window: Diagnostics, Plugins and QGIS 4, Requirements, Components, QGIS versions."""
from __future__ import annotations

import importlib
import os
from html import escape

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import compat, diagnostics, strings
from .qgis_installer import i18n as core_i18n
from .qgis_installer import requirements, runner, simulate, system
from .components_tab import ComponentsTab
from .versions_tab import VersionsTab
from .workers import FuncWorker, InstallsWorker, StepsWorker

SETTINGS = "qgis_environment_manager/"
_COLOR = {compat.OK: "#2e7d32", compat.CHECK: "#e65100", compat.NO: "#c62828"}


def plugin_dirs():
    """Where user plugins live: the profile's python/plugins and any QGIS_PLUGINPATH entries."""
    dirs = [os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")]
    dirs += [p for p in os.environ.get("QGIS_PLUGINPATH", "").split(os.pathsep) if p]
    return dirs


class EnvDialog(QDialog):
    def __init__(self, iface=None, parent=None, confirm=None, run_steps=None, facts_fn=None, dirs_fn=None,
                 sysinfo=None, load_installs=True, simulate_fn=None):
        super().__init__(parent)
        self.iface = iface
        self._simulate_fn = simulate_fn          # tests: a function steps -> result, run at once; None = ask the package manager in the background
        self._sim_workers = []
        self._confirm = confirm or self._ask
        self._run_steps = run_steps
        self._facts_fn = facts_fn or diagnostics.gather_facts
        self._dirs_fn = dirs_fn or plugin_dirs
        self._sysinfo = sysinfo
        self._load_installs = load_installs
        saved = QgsSettings().value(SETTINGS + "lang", "", str)
        self.lang = strings.resolve_lang(QgsApplication.locale(), saved)
        self.facts, self.findings, self.installs, self.rows = {}, [], None, []
        self.worker = None
        self._installs_worker = None
        self.resize(900, 640)
        self._build()
        self.refresh()

    def tr_(self, key, **kw):
        return strings.t(key, self.lang, **kw)

    # ---- UI ------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addStretch(1)
        self.btn_copy = QPushButton()
        self.btn_refresh = QPushButton()
        self.btn_lang = QPushButton()
        for b in (self.btn_copy, self.btn_refresh, self.btn_lang):
            top.addWidget(b)
        root.addLayout(top)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # diagnostics
        self.diag = QTextBrowser()
        self.tabs.addTab(self.diag, "")

        # plugins
        page = QWidget()
        lay = QVBoxLayout(page)
        self.pl_head = QLabel()
        self.pl_head.setWordWrap(True)
        self.pl_summary = QLabel()
        self.pl_summary.setWordWrap(True)
        self.chk_only = QCheckBox()
        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        for w in (self.pl_head, self.pl_summary, self.chk_only, self.table):
            lay.addWidget(w)
        self.tabs.addTab(page, "")

        # requirements
        page = QWidget()
        lay = QVBoxLayout(page)
        self.rq_head = QLabel()
        self.rq_head.setWordWrap(True)
        self.rq_tree = QTreeWidget()
        self.rq_tree.setHeaderHidden(True)
        self.rq_note = QLabel()
        self.rq_note.setWordWrap(True)
        row = QHBoxLayout()
        self.chk_optional = QCheckBox()
        self.btn_install = QPushButton()
        row.addWidget(self.chk_optional)
        row.addStretch(1)
        row.addWidget(self.btn_install)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        for w in (self.rq_head, self.rq_tree, self.rq_note):
            lay.addWidget(w)
        lay.addLayout(row)
        lay.addWidget(self.log)
        self.tabs.addTab(page, "")

        # components
        self.components = ComponentsTab(self)
        self.tabs.addTab(self.components, "")

        # versions
        self.versions = VersionsTab(self)
        self.tabs.addTab(self.versions, "")

        self.btn_lang.clicked.connect(self._toggle_lang)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_copy.clicked.connect(self._copy)
        self.chk_only.toggled.connect(self._fill_plugins)
        self.chk_optional.toggled.connect(self._fill_requirements)
        self.btn_install.clicked.connect(self._install)

    def retranslate(self):
        self.setWindowTitle(self.tr_("title"))
        self.btn_copy.setText(self.tr_("copy"))
        self.btn_refresh.setText(self.tr_("refresh"))
        self.btn_lang.setText(self.tr_("lang_btn"))
        for i, key in enumerate(("tab_diag", "tab_plugins", "tab_req", "tab_components", "tab_versions")):
            self.tabs.setTabText(i, self.tr_(key))
        self.components.retranslate()
        self.versions.retranslate()
        self.pl_head.setText(self.tr_("pl_head"))
        self.chk_only.setText(self.tr_("pl_only"))
        self.table.setHorizontalHeaderLabels(self.tr_("pl_cols"))
        self.rq_head.setText(self.tr_("rq_head"))
        self.chk_optional.setText(self.tr_("rq_with_optional"))
        self.btn_install.setText(self.tr_("rq_install"))

    # ---- data ----------------------------------------------------------------
    def refresh(self, *_):
        self.facts = self._facts_fn()
        self.rows = compat.scan(self._dirs_fn())
        self.installs = None
        self.findings = diagnostics.analyze(self.facts, None)
        self.retranslate()
        self._fill_diag()
        self._fill_plugins()
        self._fill_requirements()
        if self._load_installs and self.facts.get("is_linux"):
            self._installs_worker = InstallsWorker(self)
            self._installs_worker.done.connect(self._on_installs)
            self._installs_worker.start()

    def _on_installs(self, items):
        self.installs = items
        self.findings = diagnostics.analyze(self.facts, items)
        self._fill_diag()
        self.versions.refresh()

    def _label(self, it):
        return core_i18n.label_for(it, self.lang)

    def _fill_diag(self):
        e = escape
        h = ["<h3>{}</h3><table cellpadding='3'>".format(e(self.tr_("h_facts")))]
        for k, v in diagnostics.fact_rows(self.facts, self.lang):
            h.append("<tr><td><b>{}</b></td><td>{}</td></tr>".format(e(k), e(str(v))))
        h.append("</table><h3>{}</h3>".format(e(self.tr_("h_findings"))))
        if self.findings:
            h.append("<ul>")
            for level, key, params in self.findings:
                color = "#e65100" if level == "warn" else "#1565c0"
                h.append("<li style='color:{}'>{}</li>".format(color, e(self.tr_(key, **params))))
            h.append("</ul>")
        else:
            h.append("<p>{}</p>".format(e(self.tr_("fi_none"))))
        h.append("<h3>{}</h3>".format(e(self.tr_("h_installs"))))
        if not self.facts.get("is_linux"):
            h.append("<p>{}</p>".format(e(self.tr_("installs_off"))))
        elif self.installs is None:
            h.append("<p>{}</p>".format(e(self.tr_("installs_loading"))))
        elif not self.installs:
            h.append("<p>{}</p>".format(e(self.tr_("installs_none"))))
        else:
            h.append("<ul>" + "".join("<li>{}</li>".format(e(self._label(it))) for it in self.installs) + "</ul>")
        self.diag.setHtml("\n".join(h))

    def _qgis_major(self):
        return compat.parse_version(self.facts.get("qgis_version"), (3, 0))[0]

    def _verdict_text(self, a):
        mark = {compat.OK: self.tr_("v_ok"), compat.CHECK: self.tr_("v_check"), compat.NO: self.tr_("v_no")}
        return mark[a["status"]]

    def _fill_plugins(self, *_):
        rows = self.rows
        if self.chk_only.isChecked():
            rows = [r for r in rows if compat.assess(r, 4)["status"] != compat.OK]
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            a3, a4 = compat.assess(r, 3), compat.assess(r, 4)
            lo, hi = compat.effective_range(r)
            declared = "{} – {}".format(r["min"] or "?", r["max"] or "({}.99)".format(lo[0]))
            cells = [r["name"], r["version"], declared,
                     self.tr_("qt_yes") if r["qt6"] else self.tr_("qt_no"),
                     self._verdict_text(a3), self._verdict_text(a4)]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c in (4, 5):
                    a = a3 if c == 4 else a4
                    item.setForeground(QColor(_COLOR[a["status"]]))
                    item.setToolTip(self.tr_("why_" + a["reason"], max="{}.{}".format(*hi), min=r["min"]))
                self.table.setItem(i, c, item)
        s = compat.summarize(self.rows, 4)
        self.pl_summary.setText(self.tr_("pl_summary", ok=s[compat.OK], check=s[compat.CHECK], no=s[compat.NO])
                                if self.rows else self.tr_("pl_none"))

    # ---- requirements ---------------------------------------------------------
    def _installed_gg(self):
        have = {r["id"] for r in self.rows}
        return [p for p in requirements.PLUGIN_REQUIREMENTS if p in have]

    def _pm(self):
        info = self._sysinfo if self._sysinfo is not None else system.detect()
        return info["pm"]

    def _missing_ids(self, include_optional):
        ids = []
        for p in self._installed_gg():
            for r in requirements.status(p):
                if not r["present"] and (include_optional or not r["optional"]) and r["id"] not in ids:
                    ids.append(r["id"])
        return ids

    def _fill_requirements(self, *_):
        importlib.invalidate_caches()
        self.rq_tree.clear()
        pm = self._pm()
        names = {r["id"]: r["name"] for r in self.rows}
        plugins = self._installed_gg()
        for p in plugins:
            top = QTreeWidgetItem([names.get(p, p)])
            self.rq_tree.addTopLevelItem(top)
            for r in requirements.status(p):
                pkgs, _manual = requirements.packages_for([r["id"]], pm)
                state = self.tr_("rq_present") if r["present"] else self.tr_("rq_missing")
                opt = " ({})".format(self.tr_("rq_optional")) if r["optional"] else ""
                how = ""
                if not r["present"]:
                    how = "  →  " + (" ".join(pkgs) if pkgs else self.tr_("rq_manual"))
                QTreeWidgetItem(top, ["[{}] {}{}{}".format(state, r["label"][self.lang], opt, how)])
            top.setExpanded(True)
        missing = self._missing_ids(self.chk_optional.isChecked())
        reason = self._install_blocker(pm, missing, plugins)
        self.rq_note.setText(reason or "")
        self.btn_install.setEnabled(reason is None and not (self.worker and self.worker.isRunning()))

    def _install_blocker(self, pm, missing, plugins):
        """Why installing is not possible (text), or None when it is."""
        if not plugins:
            return self.tr_("rq_none")
        if not self.facts.get("is_linux"):
            return self.tr_("rq_no_linux")
        if self.facts.get("runtime") != "native":
            return self.tr_("rq_sandbox", kind=self.facts.get("runtime"))
        if not pm:
            return self.tr_("rq_no_pm")
        if not missing:
            return self.tr_("rq_all_ok")
        return None

    def confirm_steps(self, title, text, steps, then, log=None):
        """Show the commands, and what the package manager says they would do (a simulation, asked in the background), then ask.

        ``then()`` is called only on yes. The question appears even when the simulation could not be made: it is then said so."""
        def ask(result):
            sim = simulate.format_text(result, self.lang) if isinstance(result, dict) else ""
            body = text + ("\n\n" + sim if sim else "")
            if self._confirm(title, self.tr_("rq_confirm", text=body)):
                then()

        if self._simulate_fn is not None:
            ask(self._simulate_fn(steps))
            return
        if log is not None:
            log.appendPlainText(self.tr_("sim_checking"))
        worker = FuncWorker(lambda: simulate.explain(steps), self)
        self._sim_workers.append(worker)

        def done(result):
            self._sim_workers.remove(worker)
            ask(result)
        worker.done.connect(done)
        worker.start()

    def _ask(self, title, text) -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.StandardButton.Yes

    def _install(self):
        pm = self._pm()
        ids = self._missing_ids(self.chk_optional.isChecked())
        steps, _manual = requirements.install_steps(ids, pm)
        if not steps:
            return
        text = core_i18n.steps_text(steps, self.lang)

        def go():
            self.log.clear()
            self.log.appendPlainText(self.tr_("rq_running"))
            self.btn_install.setEnabled(False)
            self._steps = steps
            self.worker = StepsWorker(steps, runner.default_elevator(), self, self._run_steps)
            self.worker.line.connect(self.log.appendPlainText)
            self.worker.done.connect(self._on_done)
            self.worker.start()
        self.confirm_steps(self.tr_("rq_confirm_title"), text, steps, go, log=self.log)

    def _on_done(self, rc, failed):
        if rc == 0:
            self.log.appendPlainText(self.tr_("rq_done"))
        elif runner.needs_elevation_fallback(rc, failed):
            path = runner.write_root_script(self._steps)
            self.log.appendPlainText(self.tr_("rq_elev_fail", cmd="sudo sh " + path))
        else:
            self.log.appendPlainText(self.tr_("rq_failed", rc=rc))
        self._fill_requirements()

    # ---- misc -----------------------------------------------------------------
    def report(self) -> str:
        return diagnostics.report_text(self.facts, self.findings, self.installs, self.lang, self._label)

    def _copy(self):
        QApplication.clipboard().setText(self.report())
        if self.iface is not None:
            self.iface.messageBar().pushMessage("QGIS Environment Manager", self.tr_("copied"), Qgis.MessageLevel.Info, 4)

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ka" else "ka"
        QgsSettings().setValue(SETTINGS + "lang", self.lang)
        self.retranslate()
        self._fill_diag()
        self._fill_plugins()
        self._fill_requirements()
