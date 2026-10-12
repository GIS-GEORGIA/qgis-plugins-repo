import os

from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton,
    QRadioButton, QVBoxLayout)
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer)
from qgis.gui import QgsMapToolEmitPoint

from . import core, export, i18n

t = i18n.t
WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


def _spin(lo, hi, dec, value=0.0):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setValue(value)
    return s


class GeotagDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.tool = None
        self.prev_tool = None
        self.has_alt = False
        self._build()
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
        self.btn_files = QPushButton()
        self.btn_folder = QPushButton()
        self.btn_clear = QPushButton()
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
        self.use_alt = QCheckBox()
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
        fx.addWidget(self.btn_pick, 2, 3)
        root.addLayout(fx)

        self.gpx_path, self.csv_path = QLineEdit(), QLineEdit()
        self.b_gpx, self.b_csv = QPushButton(), QPushButton()
        self.b_gpx.clicked.connect(lambda: self._browse(self.gpx_path, "*.gpx"))
        self.b_csv.clicked.connect(lambda: self._browse(self.csv_path, "*.csv *.txt"))
        self.utc = _spin(-14, 14, 1, 4.0)
        self.shift = _spin(-86400, 86400, 0)
        self.gap = _spin(0, 86400, 0, 600)
        self.l_utc, self.l_shift, self.l_gap = QLabel(), QLabel(), QLabel()
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
        gx.addWidget(self.r_csv, 5, 0, 1, 3)
        gx.addWidget(self.csv_path, 6, 0, 1, 2)
        gx.addWidget(self.b_csv, 6, 2)
        root.addLayout(gx)

        self.note = QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.backup = QCheckBox()
        self.backup.setChecked(True)
        root.addWidget(self.backup)

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
        self.btn_run, self.btn_layer, self.btn_close = QPushButton(), QPushButton(), QPushButton()
        self.btn_run.clicked.connect(self._run)
        self.btn_layer.clicked.connect(self._make_output)
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_run, self.btn_layer, self.btn_close):
            btns.addWidget(b)
        root.addLayout(btns)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log)
        self.resize(640, 700)

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
        self.btn_pick.setText(t("pick"))
        self.b_gpx.setText(t("browse"))
        self.b_csv.setText(t("browse"))
        self.l_utc.setText(t("utc_offset"))
        self.l_shift.setText(t("shift"))
        self.l_gap.setText(t("max_gap"))
        self.backup.setText(t("backup"))
        self.btn_run.setText(t("run"))
        self.btn_layer.setText(t("export_btn"))
        self.note.setText(t("formats_note"))
        self.out_box.setTitle(t("output"))
        self.out_layer.setText(t("out_layer"))
        self.out_files.setText(t("out_files"))
        self.l_folder.setText(t("out_folder"))
        self.l_name.setText(t("out_name"))
        self.b_dir.setText(t("browse"))
        self.btn_close.setText(t("close"))

    def _lang_changed(self):
        i18n.set_lang(self.lang.currentData())
        self.retranslate()

    # ------------------------------------------------------------- actions
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
        if mode == 1:
            return core.load_source("gpx", file=self.gpx_path.text(), utc_offset=self.utc.value(),
                                    shift=self.shift.value(), max_gap=self.gap.value())
        if mode == 2:
            return core.load_source("csv", file=self.csv_path.text())
        if self.lat.value() == 0 and self.lon.value() == 0:
            raise core.GeotagError(t("bad_coords"))
        alt = self.alt.value() if self.use_alt.isChecked() else None
        return core.load_source("fixed", lat=self.lat.value(), lon=self.lon.value(), alt=alt)

    def _run(self):
        self.log.clear()
        photos = self._paths()
        if not photos:
            self.log.appendPlainText(t("no_files"))
            return
        try:
            if self.group.checkedId() in (1, 2) and not (
                    self.gpx_path.text() if self.group.checkedId() == 1 else self.csv_path.text()):
                raise core.GeotagError(t("no_source"))
            src = self._source()
        except core.GeotagError as exc:
            self.log.appendPlainText(t("bad_source", exc) if self.group.checkedId() else str(exc))
            return
        ok = skip = err = 0
        for p in photos:
            status, pos, detail = core.tag_photo(p, src, backup=self.backup.isChecked())
            extra = "%.6f, %.6f" % pos[:2] if pos else detail
            self.log.appendPlainText("%s: %s %s" % (p, t("res_" + status), extra))
            if status in ("ok", "ok_xmp"):
                ok += 1
            elif status == "error":
                err += 1
            else:
                skip += 1
        self.log.appendPlainText(t("summary", ok=ok, skip=skip, err=err))

    def _make_output(self):
        chosen = [k for k, cb in self.fmt_boxes.items() if cb.isChecked()]
        if not chosen and not self.out_layer.isChecked():
            self.log.appendPlainText(t("out_none"))
            return
        if chosen and not self.out_dir.text():
            self.log.appendPlainText(t("out_no_folder"))
            return
        records = core.build_records(self._paths())
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
            QgsField(k, QMetaType.Type.Double if k in ("lat", "lon", "alt") else QMetaType.Type.QString)
            for k in export.FIELDS])
        layer.updateFields()
        feats = []
        for r in records:
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r["lon"], r["lat"])))
            f.setAttributes([r[k] for k in export.FIELDS])
            feats.append(f)
        layer.dataProvider().addFeatures(feats)
        QgsProject.instance().addMapLayer(layer)
        self.log.appendPlainText(t("layer_added", len(feats)))
