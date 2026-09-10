# -*- coding: utf-8 -*-
"""ტრანსლიტერაციის დიალოგი — დირექტორია, scope, რეჟიმი, preview, შესრულება.
ორენოვანი: ზედა combo-თი ka/en გადართვა (default en)."""
from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QGuiApplication, QCursor
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QCheckBox, QRadioButton, QComboBox, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
)

from . import i18n
from . import engine

_DIR = os.path.dirname(os.path.abspath(__file__))


class TransliterateDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.lang = "en"          # ნაგულისხმევი ინგლისური
        self.plan = None
        self._build()
        self._retranslate()

    # ---- UI ----
    def _build(self):
        lay = QVBoxLayout(self)

        # language row
        top = QHBoxLayout()
        top.addStretch(1)
        self.lang_label = QLabel()
        top.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("ქართული", "ka")
        self.lang_combo.setCurrentIndex(0)           # en default
        self.lang_combo.currentIndexChanged.connect(self._on_lang)
        top.addWidget(self.lang_combo)
        lay.addLayout(top)

        # directory row
        row = QHBoxLayout()
        self.lbl_dir = QLabel()
        row.addWidget(self.lbl_dir)
        self.dir_edit = QLineEdit()
        self.dir_edit.textChanged.connect(self._sync_copy_dest)
        row.addWidget(self.dir_edit, 1)
        self.btn_browse = QPushButton()
        self.btn_browse.clicked.connect(self._browse)
        row.addWidget(self.btn_browse)
        lay.addLayout(row)

        self.recursive = QCheckBox()
        self.recursive.setChecked(True)
        lay.addWidget(self.recursive)

        # scope + mode
        two = QHBoxLayout()
        self.scope_box = QGroupBox()
        sg = QVBoxLayout(self.scope_box)
        self.cb_shp = QCheckBox(); self.cb_shp.setChecked(True)
        self.cb_db = QCheckBox(); self.cb_db.setChecked(True)
        self.cb_layers = QCheckBox(); self.cb_layers.setChecked(True)
        self.cb_fields = QCheckBox(); self.cb_fields.setChecked(True)
        for c in (self.cb_shp, self.cb_db, self.cb_layers, self.cb_fields):
            sg.addWidget(c)
        two.addWidget(self.scope_box, 1)

        self.mode_box = QGroupBox()
        mg = QGridLayout(self.mode_box)
        self.rb_inplace = QRadioButton()
        self.rb_copy = QRadioButton()
        self.rb_copy.setChecked(True)                # უსაფრთხო ნაგულისხმევი
        self.rb_copy.toggled.connect(self._toggle_copy)
        mg.addWidget(self.rb_copy, 0, 0, 1, 2)
        mg.addWidget(self.rb_inplace, 1, 0, 1, 2)
        self.copy_label = QLabel()
        self.copy_edit = QLineEdit()
        mg.addWidget(self.copy_label, 2, 0)
        mg.addWidget(self.copy_edit, 2, 1)
        two.addWidget(self.mode_box, 1)
        lay.addLayout(two)

        # preview table
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        # buttons
        btn = QHBoxLayout()
        self.about_btn = QPushButton()
        self.about_btn.clicked.connect(self._show_about)
        btn.addWidget(self.about_btn)
        self.preview_btn = QPushButton()
        self.preview_btn.clicked.connect(self.do_preview)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.do_apply)
        self.apply_btn.setEnabled(False)
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.reject)
        btn.addStretch(1)
        btn.addWidget(self.preview_btn)
        btn.addWidget(self.apply_btn)
        btn.addWidget(self.close_btn)
        lay.addLayout(btn)

    def _retranslate(self):
        L = self.lang
        self.setWindowTitle(i18n.t("title", L))
        self.lang_label.setText(i18n.t("lang_label", L))
        self.lbl_dir.setText(i18n.t("dir_label", L))
        self.btn_browse.setText(i18n.t("browse", L))
        self.recursive.setText(i18n.t("recursive", L))
        self.scope_box.setTitle(i18n.t("scope_group", L))
        self.cb_shp.setText(i18n.t("scope_shp", L))
        self.cb_db.setText(i18n.t("scope_db", L))
        self.cb_layers.setText(i18n.t("scope_layers", L))
        self.cb_fields.setText(i18n.t("scope_fields", L))
        self.mode_box.setTitle(i18n.t("mode_group", L))
        self.rb_inplace.setText(i18n.t("mode_inplace", L))
        self.rb_copy.setText(i18n.t("mode_copy", L))
        self.copy_label.setText(i18n.t("copy_dest", L))
        self.preview_btn.setText(i18n.t("preview_btn", L))
        self.apply_btn.setText(i18n.t("apply_btn", L))
        self.close_btn.setText(i18n.t("close_btn", L))
        self.about_btn.setText(i18n.t("about_btn", L))
        self.table.setHorizontalHeaderLabels([
            i18n.t("col_type", L), i18n.t("col_container", L),
            i18n.t("col_old", L), i18n.t("col_new", L)])
        # თუ preview უკვე გაკეთდა — ცხრილის ტიპები/სტატუსი ხელახლა
        if self.plan is not None:
            self._fill_table(self.plan)

    def _on_lang(self, *_):
        self.lang = self.lang_combo.currentData() or "en"
        self._retranslate()

    def _show_about(self):
        html = i18n.t("about_html", self.lang, ver=i18n.t("version", self.lang))
        box = QMessageBox(self)
        box.setWindowTitle(i18n.t("about_btn", self.lang).replace("ℹ", "").strip())
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(html)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    # ---- helpers ----
    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, i18n.t("browse", self.lang),
                                             self.dir_edit.text() or "")
        if d:
            self.dir_edit.setText(d)

    def _sync_copy_dest(self, *_):
        d = self.dir_edit.text().rstrip("/\\")
        if d and not self.copy_edit.text():
            self.copy_edit.setText(d + "_translit")

    def _toggle_copy(self, on):
        self.copy_label.setEnabled(on)
        self.copy_edit.setEnabled(on)

    def _opts(self):
        return dict(
            shp_files=self.cb_shp.isChecked(),
            db_files=self.cb_db.isChecked(),
            layers=self.cb_layers.isChecked(),
            fields=self.cb_fields.isChecked(),
            recursive=self.recursive.isChecked(),
        )

    def _loc(self, a):
        if a["kind"] in ("shp", "dbfile"):
            return a.get("dir", "")
        base = os.path.basename(a.get("db_path", ""))
        if a["kind"] == "field":
            return "{} › {}".format(base, a.get("layer", ""))
        return base

    def _fill_table(self, actions):
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            i18n.t("col_type", self.lang), i18n.t("col_container", self.lang),
            i18n.t("col_old", self.lang), i18n.t("col_new", self.lang)])
        self.table.setRowCount(0)
        for a in actions:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(i18n.kind_label(a["kind"], self.lang)))
            self.table.setItem(r, 1, QTableWidgetItem(self._loc(a)))
            self.table.setItem(r, 2, QTableWidgetItem(a["old"]))
            self.table.setItem(r, 3, QTableWidgetItem(a["new"]))

    # ---- actions ----
    def do_preview(self):
        root = self.dir_edit.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, i18n.t("title", self.lang), i18n.t("no_dir", self.lang))
            return
        opts = self._opts()
        QGuiApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            self.plan = engine.scan(root, opts["recursive"], opts)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self._fill_table(self.plan)
        if not self.plan:
            self.status.setText(i18n.t("no_changes", self.lang))
            self.apply_btn.setEnabled(False)
        else:
            self.status.setText(i18n.t("preview_count", self.lang, n=len(self.plan)))
            self.apply_btn.setEnabled(True)

    def do_apply(self):
        root = self.dir_edit.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, i18n.t("title", self.lang), i18n.t("no_dir", self.lang))
            return
        if self.plan is None:
            QMessageBox.information(self, i18n.t("title", self.lang), i18n.t("need_preview", self.lang))
            return
        n = len(self.plan)
        opts = self._opts()
        copy_to = None

        if self.rb_copy.isChecked():
            dest = self.copy_edit.text().strip()
            if not dest:
                QMessageBox.warning(self, i18n.t("title", self.lang), i18n.t("copy_dest_empty", self.lang))
                return
            if os.path.exists(dest):
                QMessageBox.warning(self, i18n.t("title", self.lang),
                                    i18n.t("copy_exists", self.lang, dest=dest))
                return
            msg = i18n.t("confirm_copy", self.lang, dest=dest, n=n)
            copy_to = dest
        else:
            msg = i18n.t("confirm_inplace", self.lang, n=n)

        if QMessageBox.question(self, i18n.t("confirm_title", self.lang), msg,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return

        QGuiApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            res = engine.apply(root, opts, copy_to=copy_to)
        except Exception as e:  # noqa: BLE001
            QGuiApplication.restoreOverrideCursor()
            QMessageBox.critical(self, i18n.t("title", self.lang), str(e))
            return
        QGuiApplication.restoreOverrideCursor()

        fails = {(a["kind"], a.get("db_path", ""), a.get("dir", ""), a["old"]): err
                 for a, err in res["failed"]}
        if fails and self.table.columnCount() == 4:
            self.table.insertColumn(4)
            self.table.setHorizontalHeaderItem(4, QTableWidgetItem("status"))
        for r, a in enumerate(self.plan):
            key = (a["kind"], a.get("db_path", ""), a.get("dir", ""), a["old"])
            if key in fails:
                self.table.setItem(r, 4, QTableWidgetItem(
                    i18n.t("status_fail", self.lang, err=fails[key])))
            elif self.table.columnCount() == 5:
                self.table.setItem(r, 4, QTableWidgetItem(i18n.t("status_ok", self.lang)))

        nfail = len(res["failed"])
        if nfail:
            self.status.setText(i18n.t("done_some", self.lang, ok=res["ok"], fail=nfail))
        else:
            self.status.setText(i18n.t("done_ok", self.lang, ok=res["ok"]))
        self.apply_btn.setEnabled(False)
        self.plan = None
