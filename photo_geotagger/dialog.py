import os

from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QRadioButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout)
from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField,
    QgsGeometry, QgsMarkerSymbol, QgsPointXY, QgsProject, QgsProperty, QgsSettings, QgsTask, QgsVectorLayer,
    QgsWkbTypes)
from qgis.gui import QgsMapToolEmitPoint

from . import core, export, i18n

t = i18n.t
WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
MAP_TIP = r'''<img src="file:///[% replace("path", '\\', '/') %]" width="320"><br>[% "file" %]'''
_FLAG = getattr(QgsTask, "Flag", QgsTask)
CAN_CANCEL = getattr(_FLAG, "CanCancel", None) or QgsTask.CanCancel


def _spin(lo, hi, dec, value=0.0):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setValue(value)
    return s


def _fmt(pos):
    if not pos:
        return ""
    text = "%.6f, %.6f" % (pos[0], pos[1])
    if pos[2] is not None:
        text += ", %.1f m" % pos[2]
    if len(pos) > 3 and pos[3] is not None:
        text += ", %.0f°" % pos[3]
    return text


class BatchTask(QgsTask):
    """Runs worker(item) for every item off the GUI thread; `done` is called on the GUI thread."""

    def __init__(self, description, items, worker, done):
        super().__init__(description, CAN_CANCEL)
        self.items, self.worker, self.done = items, worker, done
        self.results = []

    def run(self):
        total = max(len(self.items), 1)
        for i, item in enumerate(self.items):
            if self.isCanceled():
                return False
            self.results.append(self.worker(item))
            self.setProgress(100.0 * (i + 1) / total)
        return True

    def finished(self, ok):
        self.done(self.results, ok)


class GeotagDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.tool = None
        self.prev_tool = None
        self.task = None
        self._build()
        self._load_engine()
        self.retranslate()

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang = QComboBox()
        self.lang.addItem("ქართული", "ka")
        self.lang.addItem("English", "en")
        self.lang.setCurrentIndex(0 if i18n.LANG == "ka" else 1)
        self.lang.currentIndexChanged.connect(self._lang_changed)
        top.addWidget(self.lang_label)
        top.addWidget(self.lang)
        top.addStretch()
        root.addLayout(top)

        self.photos_box = QGroupBox()
        pl = QGridLayout(self.photos_box)
        self.files = QListWidget()
        self.files.setMaximumHeight(110)
        self.btn_files, self.btn_folder, self.btn_clear = QPushButton(), QPushButton(), QPushButton()
        self.btn_files.clicked.connect(self._add_files)
        self.btn_folder.clicked.connect(self._add_folder)
        self.btn_clear.clicked.connect(self.files.clear)
        pl.addWidget(self.files, 0, 0, 3, 1)
        pl.addWidget(self.btn_files, 0, 1)
        pl.addWidget(self.btn_folder, 1, 1)
        pl.addWidget(self.btn_clear, 2, 1)
        root.addWidget(self.photos_box)

        self.group = QButtonGroup(self)
        self.r_fixed, self.r_gpx, self.r_csv = QRadioButton(), QRadioButton(), QRadioButton()
        for i, r in enumerate((self.r_fixed, self.r_gpx, self.r_csv)):
            self.group.addButton(r, i)
        self.r_fixed.setChecked(True)

        self.lat, self.lon, self.alt = _spin(-90, 90, 6), _spin(-180, 180, 6), _spin(-1000, 10000, 1)
        self.heading = _spin(0, 360, 0)
        self.use_alt, self.use_dir = QCheckBox(), QCheckBox()
        self.l_lat, self.l_lon = QLabel(), QLabel()
        self.btn_pick = QPushButton()
        self.btn_pick.clicked.connect(self._pick)
        fx = QGridLayout()
        fx.addWidget(self.r_fixed, 0, 0, 1, 4)
        fx.addWidget(self.l_lat, 1, 0)
        fx.addWidget(self.lat, 1, 1)
        fx.addWidget(self.l_lon, 1, 2)
        fx.addWidget(self.lon, 1, 3)
        fx.addWidget(self.use_alt, 2, 0)
        fx.addWidget(self.alt, 2, 1)
        fx.addWidget(self.use_dir, 2, 2)
        fx.addWidget(self.heading, 2, 3)
        fx.addWidget(self.btn_pick, 3, 3)
        root.addLayout(fx)

        self.gpx_path, self.csv_path = QLineEdit(), QLineEdit()
        self.b_gpx, self.b_csv = QPushButton(), QPushButton()
        self.b_gpx.clicked.connect(lambda: self._browse(self.gpx_path, "*.gpx"))
        self.b_csv.clicked.connect(lambda: self._browse(self.csv_path, "*.csv *.txt"))
        self.utc = _spin(-14, 14, 1, 4.0)
        self.shift = _spin(-86400, 86400, 0)
        self.gap = _spin(0, 86400, 0, 600)
        self.l_utc, self.l_shift, self.l_gap = QLabel(), QLabel(), QLabel()
        self.btn_estimate = QPushButton()
        self.btn_estimate.clicked.connect(self._estimate)
        self.estimate_hint = QLabel()
        self.estimate_hint.setWordWrap(True)
        gx = QGridLayout()
        gx.addWidget(self.r_gpx, 0, 0, 1, 3)
        gx.addWidget(self.gpx_path, 1, 0, 1, 2)
        gx.addWidget(self.b_gpx, 1, 2)
        gx.addWidget(self.l_utc, 2, 0)
        gx.addWidget(self.utc, 2, 1)
        gx.addWidget(self.l_shift, 3, 0)
        gx.addWidget(self.shift, 3, 1)
        gx.addWidget(self.l_gap, 4, 0)
        gx.addWidget(self.gap, 4, 1)
        gx.addWidget(self.btn_estimate, 2, 2, 2, 1)
        gx.addWidget(self.estimate_hint, 5, 0, 1, 3)
        gx.addWidget(self.r_csv, 6, 0, 1, 3)
        gx.addWidget(self.csv_path, 7, 0, 1, 2)
        gx.addWidget(self.b_csv, 7, 2)
        root.addLayout(gx)

        self.note = QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        opts = QHBoxLayout()
        self.backup, self.overwrite = QCheckBox(), QCheckBox()
        self.backup.setChecked(True)
        opts.addWidget(self.backup)
        opts.addWidget(self.overwrite)
        root.addLayout(opts)

        self.engine_box = QGroupBox()
        el = QGridLayout(self.engine_box)
        self.engine = QComboBox()
        for key in ("auto", "builtin", "exiftool"):
            self.engine.addItem("", key)
        self.et_path = QLineEdit()
        self.b_et = QPushButton()
        self.l_et = QLabel()
        self.raw_embed = QCheckBox()
        self.et_status = QLabel()
        self.et_status.setWordWrap(True)
        self.b_et.clicked.connect(self._browse_exiftool)
        self.engine.currentIndexChanged.connect(self._apply_engine)
        self.et_path.editingFinished.connect(self._apply_engine)
        self.raw_embed.toggled.connect(self._apply_engine)
        el.addWidget(self.engine, 0, 0, 1, 3)
        el.addWidget(self.l_et, 1, 0)
        el.addWidget(self.et_path, 1, 1)
        el.addWidget(self.b_et, 1, 2)
        el.addWidget(self.raw_embed, 2, 0, 1, 3)
        el.addWidget(self.et_status, 3, 0, 1, 3)
        root.addWidget(self.engine_box)

        self.wb_box = QGroupBox()
        wl = QGridLayout(self.wb_box)
        self.wb_layer = QComboBox()
        self.wb_refresh = QPushButton("\u21bb")
        self.wb_refresh.setMaximumWidth(32)
        self.wb_refresh.clicked.connect(self._fill_layers)
        self.l_wb_layer = QLabel()
        self.wb_selected = QCheckBox()
        self.wb_hint = QLabel()
        self.wb_hint.setWordWrap(True)
        self.btn_wb = QPushButton()
        self.btn_wb.clicked.connect(self._writeback)
        wl.addWidget(self.l_wb_layer, 0, 0)
        wl.addWidget(self.wb_layer, 0, 1)
        wl.addWidget(self.wb_refresh, 0, 2)
        wl.addWidget(self.wb_selected, 1, 0, 1, 3)
        wl.addWidget(self.wb_hint, 2, 0, 1, 3)
        wl.addWidget(self.btn_wb, 3, 0, 1, 3)
        root.addWidget(self.wb_box)
        self._fill_layers()

        self.out_box = QGroupBox()
        ol = QGridLayout(self.out_box)
        self.out_layer = QCheckBox()
        self.out_layer.setChecked(True)
        self.out_files = QLabel()
        ol.addWidget(self.out_layer, 0, 0, 1, 4)
        ol.addWidget(self.out_files, 1, 0, 1, 4)
        self.fmt_boxes = {}
        for i, key in enumerate(export.available()):
            cb = QCheckBox(export.FORMATS[key][0])
            self.fmt_boxes[key] = cb
            ol.addWidget(cb, 2 + i // 4, i % 4)
        row = 3 + (len(self.fmt_boxes) - 1) // 4
        self.l_folder, self.l_name = QLabel(), QLabel()
        self.out_dir, self.out_base = QLineEdit(), QLineEdit("geotagged_photos")
        self.b_dir = QPushButton()
        self.b_dir.clicked.connect(self._browse_dir)
        ol.addWidget(self.l_folder, row, 0)
        ol.addWidget(self.out_dir, row, 1, 1, 2)
        ol.addWidget(self.b_dir, row, 3)
        ol.addWidget(self.l_name, row + 1, 0)
        ol.addWidget(self.out_base, row + 1, 1, 1, 2)
        root.addWidget(self.out_box)

        btns = QHBoxLayout()
        self.btn_preview, self.btn_run = QPushButton(), QPushButton()
        self.btn_layer, self.btn_close = QPushButton(), QPushButton()
        self.btn_cancel, self.btn_restore = QPushButton(), QPushButton()
        self.btn_cancel.setEnabled(False)
        self.btn_restore.clicked.connect(self._restore)
        self.btn_preview.clicked.connect(self._preview)
        self.btn_run.clicked.connect(self._run)
        self.btn_layer.clicked.connect(self._make_output)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_preview, self.btn_run, self.btn_layer, self.btn_restore, self.btn_cancel, self.btn_close):
            btns.addWidget(b)
        root.addLayout(btns)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.tabs = QTabWidget()
        self.table = QTableWidget(0, 5)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.tabs.addTab(self.table, "")
        self.tabs.addTab(self.log, "")
        root.addWidget(self.tabs)
        self.resize(720, 860)

    def retranslate(self):
        self.setWindowTitle(t("title"))
        self.lang_label.setText(t("lang"))
        self.photos_box.setTitle(t("photos"))
        self.btn_files.setText(t("add_files"))
        self.btn_folder.setText(t("add_folder"))
        self.btn_clear.setText(t("clear"))
        self.r_fixed.setText(t("src_coords"))
        self.r_gpx.setText(t("src_gpx"))
        self.r_csv.setText(t("src_csv"))
        self.l_lat.setText(t("lat"))
        self.l_lon.setText(t("lon"))
        self.use_alt.setText(t("alt"))
        self.use_dir.setText(t("direction"))
        self.btn_pick.setText(t("pick"))
        self.b_gpx.setText(t("browse"))
        self.b_csv.setText(t("browse"))
        self.l_utc.setText(t("utc_offset"))
        self.l_shift.setText(t("shift"))
        self.l_gap.setText(t("max_gap"))
        self.btn_estimate.setText(t("estimate"))
        self.estimate_hint.setText(t("estimate_hint"))
        self.backup.setText(t("backup"))
        self.overwrite.setText(t("overwrite"))
        self.note.setText(t("formats_note"))
        self.out_box.setTitle(t("output"))
        self.out_layer.setText(t("out_layer"))
        self.out_files.setText(t("out_files"))
        self.l_folder.setText(t("out_folder"))
        self.l_name.setText(t("out_name"))
        self.b_dir.setText(t("browse"))
        self.btn_preview.setText(t("preview"))
        self.btn_run.setText(t("run"))
        self.btn_layer.setText(t("export_btn"))
        self.btn_cancel.setText(t("cancel"))
        self.btn_restore.setText(t("restore_btn"))
        self.engine_box.setTitle(t("engine"))
        for i, key in enumerate(("engine_auto", "engine_builtin", "engine_exiftool")):
            self.engine.setItemText(i, t(key))
        self.l_et.setText(t("exiftool_path"))
        self.b_et.setText(t("browse"))
        self.raw_embed.setText(t("raw_embed"))
        self.wb_box.setTitle(t("wb_title"))
        self.l_wb_layer.setText(t("wb_layer"))
        self.wb_selected.setText(t("wb_selected"))
        self.wb_hint.setText(t("wb_hint"))
        self.btn_wb.setText(t("wb_btn"))
        self._apply_engine()
        self.btn_close.setText(t("close"))
        self.tabs.setTabText(0, t("preview"))
        self.tabs.setTabText(1, t("log"))
        self.table.setHorizontalHeaderLabels(
            [t("col_file"), t("col_taken"), t("col_existing"), t("col_new"), t("col_status")])

    def _lang_changed(self):
        i18n.set_lang(self.lang.currentData())
        self.retranslate()

    # ------------------------------------------------------------- inputs
    def _add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, t("add_files"), "", self._filter())
        self._add(names)

    @staticmethod
    def _filter():
        return "%s (%s)" % (t("photo_filter"), " ".join("*" + e for e in core.PHOTO_EXT))

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, t("out_folder"))
        if d:
            self.out_dir.setText(d)

    def _add_folder(self):
        d = QFileDialog.getExistingDirectory(self, t("add_folder"))
        if d:
            self._add(core.collect_photos([d]))

    def _add(self, paths):
        have = {self.files.item(i).text() for i in range(self.files.count())}
        self.files.addItems([p for p in paths if p not in have])

    def _paths(self):
        return [self.files.item(i).text() for i in range(self.files.count())]

    def _browse(self, edit, pattern):
        name, _ = QFileDialog.getOpenFileName(self, t("browse"), "", pattern)
        if name:
            edit.setText(name)

    def _pick(self):
        self.prev_tool = self.canvas.mapTool()
        self.tool = QgsMapToolEmitPoint(self.canvas)
        self.tool.canvasClicked.connect(self._picked)
        self.canvas.setMapTool(self.tool)
        self.iface.messageBar().pushInfo(t("title"), t("pick_hint"))
        self.hide()

    def _picked(self, point, _button):
        crs = self.canvas.mapSettings().destinationCrs()
        p = QgsCoordinateTransform(crs, WGS84, QgsProject.instance()).transform(QgsPointXY(point))
        self.lat.setValue(p.y())
        self.lon.setValue(p.x())
        self.r_fixed.setChecked(True)
        if self.prev_tool:
            self.canvas.setMapTool(self.prev_tool)
        self.show()
        self.raise_()

    def _source(self):
        mode = self.group.checkedId()
        if mode in (1, 2):
            path = self.gpx_path.text() if mode == 1 else self.csv_path.text()
            if not path:
                raise core.GeotagError(t("no_source"))
            try:
                if mode == 1:
                    return core.load_source("gpx", file=path, utc_offset=self.utc.value(),
                                            shift=self.shift.value(), max_gap=self.gap.value())
                return core.load_source("csv", file=path)
            except core.GeotagError as exc:
                raise core.GeotagError(t("bad_source", exc))
        if self.lat.value() == 0 and self.lon.value() == 0:
            raise core.GeotagError(t("bad_coords"))
        return core.load_source(
            "fixed", lat=self.lat.value(), lon=self.lon.value(),
            alt=self.alt.value() if self.use_alt.isChecked() else None,
            direction=self.heading.value() if self.use_dir.isChecked() else None)

    def _estimate(self):
        path = self.gpx_path.text()
        item = self.files.currentItem()
        if not path:
            self.log.appendPlainText(t("estimate_need_gpx"))
        elif item is None:
            self.log.appendPlainText(t("estimate_need_photo"))
        else:
            taken = core.read_datetime(item.text())
            if taken is None:
                self.log.appendPlainText(t("estimate_no_time"))
                return
            try:
                pts = core.parse_gpx(path)
            except (core.GeotagError, OSError, ValueError) as exc:
                self.log.appendPlainText(t("bad_source", exc))
                return
            offset, shift, dist = core.estimate_offset(pts, taken, self.lat.value(), self.lon.value())
            self.utc.setValue(offset)
            self.shift.setValue(round(shift))
            self.log.appendPlainText(t("estimate_done", offset, round(shift), round(dist)))
            if dist > 100:
                self.log.appendPlainText(t("estimate_far", round(dist)))
        self.tabs.setCurrentIndex(1)

    # -------------------------------------------------------- background work
    def _busy(self, on):
        for b in (self.btn_preview, self.btn_run, self.btn_layer, self.btn_restore, self.btn_wb):
            b.setEnabled(not on)
        self.btn_cancel.setEnabled(on)
        if not on:
            self.progress.setValue(0)

    def _start(self, description, items, worker, done):
        self._busy(True)

        def finished(results, ok):
            self._busy(False)
            self.task = None
            if ok:
                done(results)
            else:
                self.log.appendPlainText(t("cancelled"))
                self.tabs.setCurrentIndex(1)

        self.task = BatchTask(description, items, worker, finished)
        self.task.progressChanged.connect(lambda v: self.progress.setValue(int(v)))
        QgsApplication.taskManager().addTask(self.task)

    def _cancel(self):
        if self.task:
            self.task.cancel()

    def _prepare(self):
        """(photos, source) or None after logging why not."""
        self.log.clear()
        photos = self._paths()
        if not photos:
            self.log.appendPlainText(t("no_files"))
            self.tabs.setCurrentIndex(1)
            return None
        try:
            return photos, self._source()
        except core.GeotagError as exc:
            self.log.appendPlainText(str(exc))
            self.tabs.setCurrentIndex(1)
            return None

    def _preview(self):
        prepared = self._prepare()
        if not prepared:
            return
        photos, src = prepared
        overwrite = self.overwrite.isChecked()
        self._start(t("preview"), photos, lambda p: (p, core.plan_photo(p, src, overwrite)), self._show_preview)

    def _show_preview(self, results):
        self.table.setRowCount(len(results))
        for row, (path, (status, pos, taken, existing)) in enumerate(results):
            if status.startswith("error"):
                text = "%s: %s" % (t("res_error"), status[6:])
            else:
                text = t("would_write") if status == "ok" else t("res_" + status)
            cells = [os.path.basename(path), taken.isoformat(" ") if taken else "", _fmt(existing), _fmt(pos), text]
            for col, value in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.tabs.setCurrentIndex(0)

    def _run(self):
        prepared = self._prepare()
        if not prepared:
            return
        photos, src = prepared
        backup, overwrite = self.backup.isChecked(), self.overwrite.isChecked()
        self._start(t("run"), photos,
                    lambda p: (p, core.tag_photo(p, src, backup=backup, overwrite=overwrite)), self._show_run)

    def _show_run(self, results):
        ok = skip = err = 0
        for path, (status, pos, detail) in results:
            extra = _fmt(pos) if pos else detail
            self.log.appendPlainText("%s: %s %s" % (path, t("res_" + status), extra))
            if status in ("ok", "ok_xmp"):
                ok += 1
            elif status == "error":
                err += 1
            else:
                skip += 1
        self.log.appendPlainText(t("summary", ok=ok, skip=skip, err=err))
        self.tabs.setCurrentIndex(1)

    # --------------------------------------------------------------- engine
    def _load_engine(self):
        settings = QgsSettings()
        self.engine.setCurrentIndex(max(0, self.engine.findData(settings.value("photo_geotagger/engine", "auto"))))
        self.et_path.setText(settings.value("photo_geotagger/exiftool", "") or "")
        self.raw_embed.setChecked(str(settings.value("photo_geotagger/raw_embed", "false")).lower() == "true")

    def _browse_exiftool(self):
        name, _ = QFileDialog.getOpenFileName(self, t("exiftool_path"))
        if name:
            self.et_path.setText(name)
            self._apply_engine()

    def _apply_engine(self, *_):
        core.CONFIG.update({"engine": self.engine.currentData() or "auto", "exiftool": self.et_path.text().strip(),
                            "raw_embed": self.raw_embed.isChecked()})
        settings = QgsSettings()
        settings.setValue("photo_geotagger/engine", core.CONFIG["engine"])
        settings.setValue("photo_geotagger/exiftool", core.CONFIG["exiftool"])
        settings.setValue("photo_geotagger/raw_embed", "true" if core.CONFIG["raw_embed"] else "false")
        found = core.find_exiftool()
        self.et_status.setText(t("exiftool_found", found) if found else t("exiftool_missing"))

    # ------------------------------------------------------- layer to photos
    def _fill_layers(self):
        current = self.wb_layer.currentData()
        self.wb_layer.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and "Point" in QgsWkbTypes.displayString(layer.wkbType()):
                self.wb_layer.addItem(layer.name(), layer.id())
        index = self.wb_layer.findData(current)
        if index >= 0:
            self.wb_layer.setCurrentIndex(index)

    def showEvent(self, event):
        self._fill_layers()
        super().showEvent(event)

    def _writeback(self):
        self.tabs.setCurrentIndex(1)
        layer = QgsProject.instance().mapLayer(self.wb_layer.currentData()) if self.wb_layer.currentData() else None
        if layer is None:
            self.log.appendPlainText(t("wb_no_layer"))
            return
        names = layer.fields().names()
        if "path" not in names:
            self.log.appendPlainText(t("wb_no_field"))
            return
        to_wgs = QgsCoordinateTransform(layer.crs(), WGS84, QgsProject.instance())
        features = layer.getSelectedFeatures() if self.wb_selected.isChecked() else layer.getFeatures()

        def number(feature, name):
            value = feature[name] if name in names else None
            return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

        items = []
        for f in features:
            path = f["path"]
            if not isinstance(path, str) or not path or f.geometry().isNull():
                continue
            p = to_wgs.transform(f.geometry().asPoint())
            items.append((path, p.y(), p.x(), number(f, "alt"), number(f, "direction")))
        if not items:
            self.log.appendPlainText(t("wb_nothing"))
            return
        self.log.clear()
        backup = self.backup.isChecked()
        self._start(t("wb_btn"), items, lambda it: (it[0], core.set_position(it[0], it[1], it[2], it[3], it[4], backup)),
                    self._show_writeback)

    def _show_writeback(self, results):
        ok = same = err = 0
        for path, (status, detail) in results:
            if status == "error":
                err += 1
                self.log.appendPlainText("%s: %s %s" % (path, t("res_error"), detail))
            elif status == "same":
                same += 1
            else:
                ok += 1
                self.log.appendPlainText("%s: %s" % (path, t("res_" + status)))
        self.log.appendPlainText(t("wb_summary", ok=ok, same=same, err=err))

    # ---------------------------------------------------------------- undo
    def _restore(self):
        photos = self._paths()
        self.tabs.setCurrentIndex(1)
        if not photos:
            self.log.appendPlainText(t("no_files"))
            return
        answer = QMessageBox.question(self, t("restore_btn"), t("restore_confirm", len(photos)))
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.log.clear()
        self._start(t("restore_btn"), photos, lambda p: (p, core.restore_photo(p)), self._show_restore)

    def _show_restore(self, results):
        counts = {"restored": 0, "sidecar_removed": 0, "nothing": 0, "error": 0}
        for path, (status, detail) in results:
            counts[status] += 1
            self.log.appendPlainText("%s: %s %s" % (path, t("res_" + status), detail))
        self.log.appendPlainText(t("restore_summary", ok=counts["restored"] + counts["sidecar_removed"],
                                   skip=counts["nothing"], err=counts["error"]))

    # ------------------------------------------------------------- output
    def _make_output(self):
        chosen = [k for k, cb in self.fmt_boxes.items() if cb.isChecked()]
        self.tabs.setCurrentIndex(1)
        if not chosen and not self.out_layer.isChecked():
            self.log.appendPlainText(t("out_none"))
            return
        if chosen and not self.out_dir.text():
            self.log.appendPlainText(t("out_no_folder"))
            return
        photos = self._paths()
        self._start(t("export_btn"), photos, lambda p: core.build_records([p]),
                    lambda results: self._write_output([r for rows in results for r in rows], chosen))

    def _write_output(self, records, chosen):
        if not records:
            self.log.appendPlainText(t("layer_none"))
            return
        if self.out_layer.isChecked():
            self._project_layer(records)
        base = self.out_base.text().strip() or "geotagged_photos"
        for key in chosen:
            try:
                path = export.export_records(records, key, os.path.join(self.out_dir.text(), base))
                self.log.appendPlainText(t("out_saved", path))
            except Exception as exc:  # GDAL raises plain RuntimeError
                self.log.appendPlainText(t("out_failed", export.FORMATS[key][0], exc))

    def _project_layer(self, records):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", t("layer_name"), "memory")
        layer.dataProvider().addAttributes([
            QgsField(k, QMetaType.Type.Double if k in export.REAL_FIELDS else QMetaType.Type.QString)
            for k in export.FIELDS])
        layer.updateFields()
        feats = []
        for r in records:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r["lon"], r["lat"])))
            f.setAttributes([r[k] for k in export.FIELDS])
            feats.append(f)
        layer.dataProvider().addFeatures(feats)
        if any(r["direction"] is not None for r in records):
            symbol = QgsMarkerSymbol.createSimple(
                {"name": "arrow", "size": "6", "color": "#e5484d", "outline_color": "#ffffff"})
            symbol.setDataDefinedAngle(QgsProperty.fromField("direction"))
            layer.renderer().setSymbol(symbol)
        layer.setMapTipTemplate(MAP_TIP)
        QgsProject.instance().addMapLayer(layer)
        self.log.appendPlainText(t("layer_added", len(feats)))
