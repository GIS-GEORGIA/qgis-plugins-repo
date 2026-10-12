from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit, QPushButton,
    QRadioButton, QVBoxLayout)
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField, QgsGeometry,
    QgsPointXY, QgsProject, QgsVectorLayer)
from qgis.gui import QgsMapToolEmitPoint

from . import core, i18n

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

        self.backup = QCheckBox()
        self.backup.setChecked(True)
        root.addWidget(self.backup)

        btns = QHBoxLayout()
        self.btn_run, self.btn_layer, self.btn_close = QPushButton(), QPushButton(), QPushButton()
        self.btn_run.clicked.connect(self._run)
        self.btn_layer.clicked.connect(self._add_layer)
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
        self.btn_layer.setText(t("add_layer"))
        self.btn_close.setText(t("close"))

    def _lang_changed(self):
        i18n.set_lang(self.lang.currentData())
        self.retranslate()

    # ------------------------------------------------------------- actions
    def _add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, t("add_files"), "", t("photo_filter"))
        self._add(names)

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
            if status == "ok":
                ok += 1
            elif status == "error":
                err += 1
            else:
                skip += 1
        self.log.appendPlainText(t("summary", ok=ok, skip=skip, err=err))

    def _add_layer(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", t("layer_name"), "memory")
        layer.dataProvider().addAttributes([
            QgsField("file", QMetaType.Type.QString), QgsField("path", QMetaType.Type.QString),
            QgsField("alt", QMetaType.Type.Double), QgsField("taken", QMetaType.Type.QString)])
        layer.updateFields()
        feats = []
        for p in self._paths():
            try:
                pos = core.read_gps(p)
                taken = core.read_datetime(p)
            except (core.GeotagError, OSError, ValueError):
                continue
            if not pos:
                continue
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pos[1], pos[0])))
            f.setAttributes([p.replace("\\", "/").split("/")[-1], p, pos[2],
                             taken.isoformat(" ") if taken else None])
            feats.append(f)
        if not feats:
            self.log.appendPlainText(t("layer_none"))
            return
        layer.dataProvider().addFeatures(feats)
        QgsProject.instance().addMapLayer(layer)
        self.log.appendPlainText(t("layer_added", len(feats)))
