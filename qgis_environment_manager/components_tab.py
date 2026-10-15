# -*- coding: utf-8 -*-
"""The "Components" tab: the programs and libraries around QGIS (GDAL, PROJ, GRASS, SAGA, Python libraries, database clients),
what is there and what can be added, installed with the system's package manager - the small Linux form of the OSGeo4W chooser.

Only installing: nothing here removes packages (a library such as NumPy can be a dependency of QGIS itself). The commands are
shown first and run only after confirmation; a sandboxed QGIS (Flatpak, Snap) or a system that is not Linux gets an explanation.
"""
from __future__ import annotations

import importlib

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .qgis_installer import i18n as core_i18n
from .qgis_installer import requirements, runner, system
from .workers import StepsWorker

ROLE_ID = Qt.ItemDataRole.UserRole


class ComponentsTab(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.d = dialog
        self._info = None                          # tests inject a system description
        self.worker = None
        self._steps: list = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setWordWrap(True)
        self.blocker = QLabel()
        self.blocker.setWordWrap(True)
        self.blocker.setStyleSheet("color:#b42318")
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        row = QHBoxLayout()
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.btn_install = QPushButton()
        row.addWidget(self.note, 1)
        row.addWidget(self.btn_install)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.head)
        lay.addWidget(self.blocker)
        lay.addWidget(self.tree, 1)
        lay.addLayout(row)
        lay.addWidget(self.log)
        self.tree.itemChanged.connect(self._on_changed)
        self.btn_install.clicked.connect(self.run_install)

    def tr_(self, key, **kw):
        return self.d.tr_(key, **kw)

    def core(self, key, **kw):
        return core_i18n.t(key, self.d.lang, **kw)

    def sysinfo(self):
        return self._info or system.detect()

    def blocked(self):
        f = self.d.facts
        if not f.get("is_linux"):
            return self.tr_("rq_no_linux")
        if f.get("runtime") != "native":
            return self.tr_("rq_sandbox", kind=f.get("runtime"))
        if not self.sysinfo()["pm"]:
            return self.tr_("rq_no_pm")
        return None

    def retranslate(self):
        self.head.setText(self.tr_("cp_head"))
        self.btn_install.setText(self.tr_("cp_install_btn"))
        self.refresh()

    # ---- the list ----------------------------------------------------------------
    def refresh(self):
        importlib.invalidate_caches()
        reason = self.blocked()
        self.blocker.setText(reason or "")
        self.blocker.setVisible(bool(reason))
        pm = self.sysinfo()["pm"]
        checked = set(self.selected()) if self.tree.topLevelItemCount() else set()
        self.tree.blockSignals(True)
        self.tree.clear()
        for cat in requirements.CATEGORIES:
            rows = [r for r in requirements.components(pm) if r["cat"] == cat]
            top = QTreeWidgetItem([self.core("cat_" + cat)])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(top)
            for r in rows:
                if r["present"]:
                    state, how = self.tr_("rq_present"), ""
                elif r["packages"]:
                    state, how = self.tr_("rq_missing"), "  →  " + " ".join(r["packages"])
                else:
                    state, how = self.tr_("rq_missing"), "  →  " + self.tr_("rq_manual")
                item = QTreeWidgetItem(top, ["[{}] {}{}".format(state, r["label"][self.d.lang], how)])
                item.setData(0, ROLE_ID, r["id"])
                can = (not r["present"]) and bool(r["packages"]) and reason is None
                if can:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(0, Qt.CheckState.Checked if r["id"] in checked else Qt.CheckState.Unchecked)
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            top.setExpanded(True)
        self.tree.blockSignals(False)
        self._on_changed()

    def selected(self):
        ids = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable and it.checkState(0) == Qt.CheckState.Checked:
                    ids.append(it.data(0, ROLE_ID))
        return ids

    def _on_changed(self, *_):
        n = len(self.selected())
        self.note.setText(self.tr_("cp_selected", n=n) if n else self.tr_("cp_none_selected"))
        self.btn_install.setEnabled(n > 0 and self.blocked() is None and not self._running())

    def _running(self):
        return bool(self.worker and self.worker.isRunning())

    # ---- install -----------------------------------------------------------------
    def run_install(self):
        ids = self.selected()
        if not ids or self.blocked() is not None or self._running():
            return
        steps, _manual = requirements.install_steps(ids, self.sysinfo()["pm"])
        if not steps:
            return
        text = core_i18n.steps_text(steps, self.d.lang)

        def go():
            self.log.clear()
            self.log.appendPlainText(self.tr_("rq_running"))
            self._steps = steps
            self.btn_install.setEnabled(False)
            self.worker = StepsWorker(steps, runner.default_elevator(), self, self.d._run_steps)
            self.worker.line.connect(self.log.appendPlainText)
            self.worker.done.connect(self._on_done)
            self.worker.start()
        self.d.confirm_steps(self.tr_("rq_confirm_title"), text, steps, go, log=self.log)

    def _on_done(self, rc, failed):
        if rc == 0:
            self.log.appendPlainText(self.tr_("rq_done"))
        elif runner.needs_elevation_fallback(rc, failed):
            self.log.appendPlainText(self.tr_("rq_elev_fail", cmd="sudo sh " + runner.write_root_script(self._steps)))
        else:
            self.log.appendPlainText(self.tr_("rq_failed", rc=rc))
        self.refresh()
        self.d._fill_requirements()
