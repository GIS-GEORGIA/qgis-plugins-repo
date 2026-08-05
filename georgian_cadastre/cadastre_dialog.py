# -*- coding: utf-8 -*-
"""The plugin dialog — bilingual (ka/en), asynchronous.

Single tab : code -> (picker if several) -> add to map / export SHP·DXF·CSV.
Batch tab  : many codes -> one combined layer.
Reverse    : click the map to resolve the parcel under the cursor.

All network work runs on background QgsTasks (proxy-aware) so the UI never
freezes.
"""
import os

from qgis.core import QgsApplication, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import cadastre_core as core
from . import i18n
from . import tasks


def _detect_lang():
    """Default to the QGIS UI locale if it is English, otherwise Georgian."""
    try:
        loc = QgsSettings().value("locale/userLocale", "") or ""
    except Exception:  # noqa: BLE001
        loc = ""
    return "en" if loc.lower().startswith("en") else "ka"


class CadastreDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.lang = _detect_lang()
        self._result = None      # resolved single result (see tasks._resolve_match)
        self._matches = []       # search matches for the picker
        self._tasks = []         # keep references so tasks aren't GC'd
        self._map_tool = None
        self._prev_tool = None

        self.setMinimumWidth(460)
        self._build_ui()
        self._retranslate()
        self._set_ready(False)

    def _t(self, key, *args):
        return i18n.t(key, self.lang, *args)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # language selector (top-right)
        top = QHBoxLayout()
        top.addStretch(1)
        self.lang_lbl = QLabel()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem(u"ქართული", "ka")
        self.lang_combo.addItem(u"English", "en")
        self.lang_combo.setCurrentIndex(0 if self.lang == "ka" else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        top.addWidget(self.lang_lbl)
        top.addWidget(self.lang_combo)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_single_tab(), "")
        self.tabs.addTab(self._build_batch_tab(), "")
        root.addWidget(self.tabs)

        # shared options
        opt = QHBoxLayout()
        self.crs_lbl = QLabel()
        self.crs_combo = QComboBox()
        for label, epsg in core.CRS_CHOICES:
            self.crs_combo.addItem(label, epsg)
        opt.addWidget(self.crs_lbl)
        opt.addWidget(self.crs_combo, 1)
        root.addLayout(opt)

        self.info_check = QCheckBox()
        self.info_check.setChecked(True)
        root.addWidget(self.info_check)

        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("color: gray; font-size: 11px;")
        self.status_lbl.setWordWrap(True)
        root.addWidget(self.status_lbl)

    def _build_single_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        self.code_lbl = QLabel()
        lay.addWidget(self.code_lbl)
        row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("38.10.42.107")
        self.code_edit.returnPressed.connect(self.on_search)
        self.search_btn = QPushButton()
        self.search_btn.clicked.connect(self.on_search)
        self.reverse_btn = QPushButton()
        self.reverse_btn.setCheckable(True)
        self.reverse_btn.clicked.connect(self.on_reverse_toggle)
        row.addWidget(self.code_edit)
        row.addWidget(self.search_btn)
        row.addWidget(self.reverse_btn)
        lay.addLayout(row)

        # picker for multiple matches (hidden until needed)
        self.match_combo = QComboBox()
        self.match_combo.setVisible(False)
        self.match_combo.currentIndexChanged.connect(self._on_match_picked)
        lay.addWidget(self.match_combo)

        self.info_lbl = QLabel("")
        self.info_lbl.setWordWrap(True)
        self.info_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.info_lbl)

        self.abox = QGroupBox()
        grid = QGridLayout(self.abox)
        self.add_btn = QPushButton()
        self.shp_btn = QPushButton()
        self.dxf_btn = QPushButton()
        self.csv_btn = QPushButton()
        self.add_btn.clicked.connect(self.on_add_to_map)
        self.shp_btn.clicked.connect(lambda: self.on_export("SHP"))
        self.dxf_btn.clicked.connect(lambda: self.on_export("DXF"))
        self.csv_btn.clicked.connect(lambda: self.on_export("CSV"))
        grid.addWidget(self.add_btn, 0, 0, 1, 3)
        grid.addWidget(self.shp_btn, 1, 0)
        grid.addWidget(self.dxf_btn, 1, 1)
        grid.addWidget(self.csv_btn, 1, 2)
        lay.addWidget(self.abox)
        lay.addStretch(1)
        return w

    def _build_batch_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.batch_lbl = QLabel()
        lay.addWidget(self.batch_lbl)
        self.batch_edit = QPlainTextEdit()
        self.batch_edit.setPlaceholderText("38.10.42.107\n01.10.01.001")
        lay.addWidget(self.batch_edit)
        row = QHBoxLayout()
        self.batch_file_btn = QPushButton()
        self.batch_file_btn.clicked.connect(self.on_batch_from_file)
        self.batch_run_btn = QPushButton()
        self.batch_run_btn.clicked.connect(self.on_batch_run)
        row.addWidget(self.batch_file_btn)
        row.addStretch(1)
        row.addWidget(self.batch_run_btn)
        lay.addLayout(row)
        return w

    def _retranslate(self):
        self.setWindowTitle(self._t("window_title"))
        self.lang_lbl.setText(self._t("lang_label"))
        self.tabs.setTabText(0, self._t("tab_single"))
        self.tabs.setTabText(1, self._t("tab_batch"))
        self.code_lbl.setText(self._t("code_label"))
        self.search_btn.setText(self._t("search_btn"))
        self.reverse_btn.setText(self._t("reverse_btn"))
        self.crs_lbl.setText(self._t("crs_label"))
        self.info_check.setText(self._t("more_info"))
        self.abox.setTitle(self._t("actions_group"))
        self.add_btn.setText(self._t("add_btn"))
        self.shp_btn.setText(self._t("shp_btn"))
        self.dxf_btn.setText(self._t("dxf_btn"))
        self.csv_btn.setText(self._t("csv_btn"))
        self.batch_lbl.setText(self._t("batch_label"))
        self.batch_file_btn.setText(self._t("batch_from_file"))
        self.batch_run_btn.setText(self._t("batch_run"))
        if self._result:
            self._show_result()
        elif not self.status_lbl.text():
            self.status_lbl.setText(self._t("source"))

    def _on_lang_changed(self, _idx):
        self.lang = self.lang_combo.currentData() or "ka"
        self._retranslate()

    def _set_ready(self, ready):
        for wgt in (self.add_btn, self.shp_btn, self.dxf_btn, self.csv_btn):
            wgt.setEnabled(ready)

    def _want_info(self):
        return self.info_check.isChecked()

    # ------------------------------------------------------- task plumbing
    def _run(self, task, on_ok, busy_msg=None):
        """Wire a CallTask's signals, keep a reference, and queue it."""
        if busy_msg:
            self.status_lbl.setText(busy_msg)

        def _done():
            self._tasks.remove(task) if task in self._tasks else None
            if task.error is not None:
                self._show_task_error(task.error)
            else:
                on_ok(task.result)

        task.taskCompleted.connect(_done)
        task.taskTerminated.connect(_done)
        self._tasks.append(task)
        QgsApplication.taskManager().addTask(task)

    def _show_task_error(self, exc):
        key = getattr(exc, "key", None)
        detail = getattr(exc, "detail", "")
        msg = self._t(key, detail) if key else str(exc)
        self.info_lbl.setText(u"⚠ {}".format(msg))
        self.status_lbl.setText(self._t("source"))

    # --------------------------------------------------------- single flow
    def on_search(self):
        code = self.code_edit.text().strip()
        if not code:
            return
        self._reset_single()
        self.search_btn.setEnabled(False)
        self.info_lbl.setText(self._t("searching"))
        self._run(tasks.search_task(code), self._on_search_done)

    def _reset_single(self):
        self._result = None
        self._matches = []
        self.match_combo.blockSignals(True)
        self.match_combo.clear()
        self.match_combo.setVisible(False)
        self.match_combo.blockSignals(False)
        self._set_ready(False)

    def _on_search_done(self, matches):
        self.search_btn.setEnabled(True)
        self._matches = matches or []
        if not self._matches:
            self.info_lbl.setText(u"⚠ {}".format(
                self._t("err_not_found", self.code_edit.text().strip())))
            return
        if len(self._matches) > 1:
            self.match_combo.blockSignals(True)
            self.match_combo.clear()
            for m in self._matches:
                label = m["code"]
                if m.get("address"):
                    label += u" — " + m["address"]
                self.match_combo.addItem(label)
            self.match_combo.setVisible(True)
            self.match_combo.setCurrentIndex(0)
            self.match_combo.blockSignals(False)
            self.info_lbl.setText(self._t("multiple_found", len(self._matches)))
        self._load_match(self._matches[0])

    def _on_match_picked(self, idx):
        if 0 <= idx < len(self._matches):
            self._load_match(self._matches[idx])

    def _load_match(self, match):
        self._set_ready(False)
        self.info_lbl.setText(self._t("searching"))
        self._run(tasks.features_task(match, self._want_info()),
                  self._on_features_done)

    def _on_features_done(self, result):
        self._result = result
        self._auto_select_zone()
        self._show_result()
        self._set_ready(True)

    def _show_result(self):
        r = self._result
        addr = r["address"] or self._t("no_address")
        html = u"<b>{}</b><br>{}".format(r["code"], addr)
        info = r.get("info") or {}
        if info.get("area_official") is not None:
            html += u"<br>" + self._t(
                "area_line",
                info.get("area_official"),
                info.get("parcel_type", "—") or "—",
                info.get("status", "") or "",
            )
        if len(r.get("features", [])) > 1:
            html += u"  ({}×)".format(len(r["features"]))
        self.info_lbl.setText(html)

    def _auto_select_zone(self):
        try:
            geom = core.geometry_from_wkt(self._result["features"][0]["wkt"])
            epsg = core.auto_zone_epsg(geom)
        except Exception:  # noqa: BLE001
            return
        idx = self.crs_combo.findData(epsg)
        if idx >= 0:
            self.crs_combo.setCurrentIndex(idx)

    def _target_epsg(self):
        return self.crs_combo.currentData()

    def _current_layer(self):
        r = self._result
        return core.build_layer(
            r["features"], r["code"], r["address"],
            self._target_epsg(), info=r.get("info"),
        )

    def on_add_to_map(self):
        if not self._result:
            return
        try:
            layer = self._current_layer()
            core.add_to_project(layer)
            if self.iface is not None:
                self.iface.mapCanvas().setExtent(layer.extent())
                self.iface.mapCanvas().refresh()
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        self.status_lbl.setText(self._t("added", self._result["code"]))

    def on_export(self, fmt):
        if not self._result:
            return
        ext = {"SHP": "shp", "DXF": "dxf", "CSV": "csv"}[fmt]
        default_name = "{}.{}".format(self._result["code"].replace(".", "_"), ext)
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("save_title", fmt), default_name,
            "{0} (*.{1})".format(fmt, ext),
        )
        if not path:
            return
        if not path.lower().endswith("." + ext):
            path += "." + ext
        try:
            layer = self._current_layer()
            err = core.export_csv_vertices(layer, path) if fmt == "CSV" \
                else core.export_layer(layer, fmt, path)
        except Exception as exc:  # noqa: BLE001
            self._error(str(exc))
            return
        if err:
            msg = self._t(err) if err == "err_empty_layer" \
                else self._t("err_write", err)
            QMessageBox.warning(self, self._t("error_title"), msg)
        else:
            self.status_lbl.setText(self._t("saved", os.path.basename(path)))

    # ------------------------------------------------------- reverse lookup
    def on_reverse_toggle(self, checked):
        if self.iface is None:
            self.reverse_btn.setChecked(False)
            return
        canvas = self.iface.mapCanvas()
        if checked:
            from .map_tool import ParcelClickTool
            self._prev_tool = canvas.mapTool()
            self._map_tool = ParcelClickTool(canvas)
            self._map_tool.pointClicked.connect(self._on_map_point)
            canvas.setMapTool(self._map_tool)
            self.status_lbl.setText(self._t("reverse_on"))
        else:
            self._deactivate_tool()

    def _deactivate_tool(self):
        if self.iface is not None and self._map_tool is not None:
            canvas = self.iface.mapCanvas()
            if self._prev_tool is not None:
                canvas.setMapTool(self._prev_tool)
            else:
                canvas.unsetMapTool(self._map_tool)
        self._map_tool = None
        self.reverse_btn.setChecked(False)

    def _on_map_point(self, lon, lat):
        self._deactivate_tool()
        self.tabs.setCurrentIndex(0)
        self.info_lbl.setText(self._t("searching"))
        self._run(tasks.reverse_task(lon, lat), self._on_reverse_done)

    def _on_reverse_done(self, parcels):
        self._reset_single()
        if not parcels:
            self.info_lbl.setText(u"⚠ {}".format(self._t("err_no_geom")))
            return
        # Reuse the match-picker machinery.
        self._on_search_done(parcels)

    # --------------------------------------------------------- batch flow
    def on_batch_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("open_codes"), "", "Text/CSV (*.txt *.csv);;All (*.*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as fh:
                text = fh.read()
        except OSError as exc:
            self._error(str(exc))
            return
        # Accept comma/space/newline separated; keep code-like tokens.
        import re
        tokens = re.split(r"[\s,;]+", text)
        codes = [tok for tok in tokens if tok]
        self.batch_edit.setPlainText("\n".join(codes))

    def _batch_codes(self):
        raw = self.batch_edit.toPlainText()
        seen, out = set(), []
        for line in raw.splitlines():
            code = line.strip()
            if code and code not in seen:
                seen.add(code)
                out.append(code)
        return out

    def on_batch_run(self):
        codes = self._batch_codes()
        if not codes:
            QMessageBox.information(self, self._t("window_title"),
                                    self._t("batch_empty"))
            return
        self.batch_run_btn.setEnabled(False)
        self.status_lbl.setText(self._t("batch_progress", 0, len(codes)))
        task = tasks.BatchTask(codes, with_info=self._want_info())
        self._run(task, self._on_batch_done)

    def _on_batch_done(self, results):
        self.batch_run_btn.setEnabled(True)
        results = results or []
        ok = [r for r in results if r.get("ok")]
        fail = [r for r in results if not r.get("ok")]

        if ok:
            target = self._target_epsg()
            merged = None
            for r in ok:
                d = r["data"]
                layer = core.build_layer(d["features"], d["code"], d["address"],
                                         target, info=d.get("info"))
                if merged is None:
                    merged = layer
                    merged.setName(self._t("batch_layer_name"))
                    merged.startEditing()
                else:
                    for feat in layer.getFeatures():
                        merged.dataProvider().addFeature(feat)
            if merged is not None:
                merged.commitChanges()
                merged.updateExtents()
                core.add_to_project(merged)
                if self.iface is not None:
                    self.iface.mapCanvas().setExtent(merged.extent())
                    self.iface.mapCanvas().refresh()

        self.status_lbl.setText(self._t("batch_done", len(ok), len(fail)))
        if fail:
            detail = "\n".join(u"{}: {}".format(r["code"], r.get("error", ""))
                               for r in fail)
            QMessageBox.warning(self, self._t("error_title"), detail)

    # --------------------------------------------------------------- misc
    def _error(self, detail):
        QMessageBox.critical(self, self._t("error_title"), detail)

    def closeEvent(self, event):
        self._deactivate_tool()
        super().closeEvent(event)
