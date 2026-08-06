# -*- coding: utf-8 -*-
"""Tabbed, bilingual (KA/EN) control panel for the plugin.

Thin GUI layer: every button delegates to a core.* module and reports the
result on the QGIS message bar. Rebuildable on language switch.
"""

import os
import webbrowser

from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QTabWidget, QWidget, QLabel, QPushButton, QLineEdit, QComboBox,
    QFileDialog, QCheckBox, QSpinBox, QDateEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QMessageBox, QApplication, QGroupBox,
)
from qgis.core import QgsProject, QgsSettings, Qgis

from .core import config, i18n
from .core import crs as crs_mod
from .core import templates as tpl
from .core import styles as styles_mod
from .core import services as services_mod
from .core import database as db_mod
from .core import fonts as fonts_mod
from .core import layout as layout_mod
from .core import excel as excel_mod
from .core import export as export_mod
from .core import repo_assets as repo_mod
from .core import fetch as fetch_mod
from .. import napr_client

_tr = i18n.tr


class CadastralDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setMinimumSize(680, 560)
        self._settings = QgsSettings()
        # A single persistent root layout; the whole UI lives in one swappable
        # container widget so language switches rebuild cleanly (no ghost
        # widgets left behind by a partial teardown).
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(6, 6, 6, 6)
        self._container = None
        self._build_ui()

    # ------------------------------------------------------------------ UI #
    def _build_ui(self):
        self.setWindowTitle(_tr("plugin_title"))
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)

        # Header: title + language switch (one combo, on the right)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{_tr('plugin_title')}</b>"))
        header.addStretch(1)
        header.addWidget(QLabel(_tr("language") + ":"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("ქართული", "ka")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.setCurrentIndex(0 if i18n.current_language() == "ka" else 1)
        # Connect AFTER setCurrentIndex so building doesn't fire a switch.
        self.lang_combo.currentIndexChanged.connect(self._switch_language)
        header.addWidget(self.lang_combo)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_project(), _tr("tab_project"))
        self.tabs.addTab(self._tab_fetch(), _tr("tab_fetch"))
        self.tabs.addTab(self._tab_services(), _tr("tab_services"))
        self.tabs.addTab(self._tab_data(), _tr("tab_data"))
        self.tabs.addTab(self._tab_layout(), _tr("tab_layout"))
        self.tabs.addTab(self._tab_attachment(), _tr("tab_attachment"))
        self.tabs.addTab(self._tab_settings(), _tr("tab_settings"))
        root.addWidget(self.tabs)

        self._root.addWidget(container)
        self._container = container

    def _switch_language(self):
        lang = self.lang_combo.currentData()
        if lang == i18n.current_language():
            return
        i18n.set_language(lang)
        # Swap the entire container: deleting it removes every child widget,
        # so no old header/combo survives.
        old = self._container
        self._container = None
        if old is not None:
            self._root.removeWidget(old)
            old.setParent(None)
            old.deleteLater()
        self._build_ui()

    # -------------------------------------------------------- shared bits #
    def _dir_row(self, initial_key="work_dir"):
        row = QHBoxLayout()
        edit = QLineEdit(self._settings.value(f"{config.SETTINGS_GROUP}/{initial_key}", ""))
        btn = QPushButton(_tr("browse"))

        def pick():
            d = QFileDialog.getExistingDirectory(self, _tr("output_dir"), edit.text())
            if d:
                edit.setText(d)
                self._settings.setValue(f"{config.SETTINGS_GROUP}/{initial_key}", d)
        btn.clicked.connect(pick)
        row.addWidget(edit, 1)
        row.addWidget(btn)
        return row, edit

    def _zone_combo(self):
        combo = QComboBox()
        combo.addItem(_tr("zone_38"), 38)
        combo.addItem(_tr("zone_37"), 37)
        saved = int(self._settings.value(f"{config.SETTINGS_GROUP}/zone", config.DEFAULT_ZONE))
        combo.setCurrentIndex(0 if saved == 38 else 1)
        combo.currentIndexChanged.connect(
            lambda: self._settings.setValue(f"{config.SETTINGS_GROUP}/zone", combo.currentData()))
        return combo

    def _msg(self, text, level=Qgis.Info):
        self.iface.messageBar().pushMessage(_tr("plugin_title"), text, level=level, duration=6)

    # --------------------------------------------------------- Project tab #
    def _tab_project(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        form = QFormLayout()
        self.zone_combo = self._zone_combo()
        form.addRow(_tr("zone"), self.zone_combo)
        dir_row, self.work_dir = self._dir_row("work_dir")
        form.addRow(_tr("output_dir"), self._wrap(dir_row))
        lay.addLayout(form)

        btn_repo = QPushButton("↧ " + _tr("download_templates_repo"))
        btn_repo.clicked.connect(self._on_download_templates_repo)
        lay.addWidget(btn_repo)
        lay.addWidget(self._hint(_tr("repo_templates_hint")))

        btn_tpl = QPushButton(_tr("create_templates"))
        btn_tpl.clicked.connect(self._on_create_templates)
        lay.addWidget(btn_tpl)
        lay.addWidget(self._hint(_tr("create_templates_hint")))

        btn_style = QPushButton(_tr("apply_styles"))
        btn_style.clicked.connect(self._on_apply_styles)
        lay.addWidget(btn_style)

        lay.addStretch(1)
        return w

    def _on_download_templates_repo(self):
        out = self.work_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        zone = self.zone_combo.currentData()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            crs_mod.set_project_crs(zone)
            saved = []
            for cat in ("cadastre_shp", "floorplan_shp"):
                saved += repo_mod.download_category(cat, os.path.join(out, cat))
            # Load every downloaded shapefile, grouped, and style by name.
            project = QgsProject.instance()
            root = project.layerTreeRoot()
            grp = root.insertGroup(0, f"Templates (UTM {zone}N)")
            from qgis.core import QgsVectorLayer
            loaded = 0
            for shp in sorted(set(repo_mod.find_shapefiles(out))):
                name = os.path.splitext(os.path.basename(shp))[0]
                lyr = QgsVectorLayer(shp, name, "ogr")
                if not lyr.isValid():
                    continue
                project.addMapLayer(lyr, addToLegend=False)
                grp.insertLayer(0, lyr)
                styles_mod.apply_style(lyr)
                loaded += 1
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._msg(f"{_tr('done')}: {len(saved)} file(s), {loaded} layer(s).")

    def _on_create_templates(self):
        out = self.work_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        zone = self.zone_combo.currentData()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            crs_mod.set_project_crs(zone)
            paths = tpl.create_all(out, zone, overwrite=False)
            layers = tpl.add_to_project(paths, group_name=f"UTM {zone}N")
            for l in layers:
                styles_mod.apply_style(l)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._msg(f"{_tr('done')}: {len(paths)} templates (UTM {zone}N).")

    def _on_apply_styles(self):
        applied = styles_mod.apply_to_project(QgsProject.instance())
        self.iface.mapCanvas().refreshAllLayers()
        self._msg(f"{_tr('done')}: {', '.join(applied) or '—'}")

    # ----------------------------------------------------------- Fetch tab #
    def _tab_fetch(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("38.10.42.107")
        self.code_edit.returnPressed.connect(self._on_fetch_code)
        form.addRow(_tr("cad_code"), self.code_edit)
        lay.addLayout(form)

        row = QHBoxLayout()
        btn_fetch = QPushButton("↧ " + _tr("fetch_btn"))
        btn_fetch.clicked.connect(self._on_fetch_code)
        btn_rev = QPushButton("⊕ " + _tr("reverse_btn"))
        btn_rev.clicked.connect(self._on_reverse)
        row.addWidget(btn_fetch)
        row.addWidget(btn_rev)
        lay.addLayout(row)
        lay.addWidget(self._hint(_tr("fetch_hint")))

        btn_adv = QPushButton(_tr("advanced_fetch"))
        btn_adv.clicked.connect(self._on_advanced_fetch)
        lay.addWidget(btn_adv)
        lay.addStretch(1)
        self._map_tool = None
        self._napr_dlg = None
        return w

    def _fetch_zone(self):
        if hasattr(self, "zone_combo"):
            return self.zone_combo.currentData()
        return int(self._settings.value(f"{config.SETTINGS_GROUP}/zone",
                                        config.DEFAULT_ZONE))

    def _insert_features(self, features, code, address, zone):
        area = 0.0
        layer = None
        for f in features:
            epsg = str(f.get("epsg") or "EPSG:4326")
            if not epsg.upper().startswith("EPSG:"):
                epsg = "EPSG:" + epsg
            area, layer = fetch_mod.add_parcel(
                QgsProject.instance(), zone, f["wkt"], code, address, src_epsg=epsg)
        if layer is not None and self.iface is not None:
            self.iface.mapCanvas().setExtent(layer.extent())
            self.iface.mapCanvas().refresh()
        return area

    def _on_fetch_code(self):
        code = self.code_edit.text().strip()
        if not code:
            return self._msg(_tr("no_code"), Qgis.Warning)
        zone = self._fetch_zone()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = napr_client.lookup(code)
            crs_mod.set_project_crs(zone)
            area = self._insert_features(
                result["features"], result["code"], result.get("address") or "", zone)
        except napr_client.NaprError as exc:
            QApplication.restoreOverrideCursor()
            return self._msg(f"{code}: {' '.join(str(a) for a in exc.args)}", Qgis.Warning)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._msg(_tr("fetched_ok", code=result["code"], area=round(area)))

    def _on_reverse(self):
        if self.iface is None:
            return
        from ..map_tool import ParcelClickTool
        canvas = self.iface.mapCanvas()
        self._map_tool = ParcelClickTool(canvas)
        self._map_tool.pointClicked.connect(self._on_map_point)
        canvas.setMapTool(self._map_tool)
        self._msg(_tr("reverse_on"))

    def _on_map_point(self, lon, lat):
        canvas = self.iface.mapCanvas()
        if self._map_tool is not None:
            canvas.unsetMapTool(self._map_tool)
        zone = self._fetch_zone()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matches = napr_client.reverse(lon, lat)
            if not matches:
                QApplication.restoreOverrideCursor()
                return self._msg(_tr("error"), Qgis.Warning)
            m = matches[0]
            feats = napr_client.fetch_features(m["lbl"])
            crs_mod.set_project_crs(zone)
            area = self._insert_features(feats, m.get("code", ""), m.get("address", ""), zone)
        except napr_client.NaprError as exc:
            QApplication.restoreOverrideCursor()
            return self._msg(" ".join(str(a) for a in exc.args), Qgis.Warning)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._msg(_tr("fetched_ok", code=m.get("code", ""), area=round(area)))

    def _on_advanced_fetch(self):
        """Open the full NAPR dialog (batch, reverse, SHP/DXF/CSV export)."""
        if self._napr_dlg is None:
            from ..cadastre_dialog import CadastreDialog
            self._napr_dlg = CadastreDialog(self.iface, self)
        self._napr_dlg.show()
        self._napr_dlg.raise_()
        self._napr_dlg.activateWindow()

    # -------------------------------------------------------- Services tab #
    def _tab_services(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(_tr("available_services")))
        self.svc_list = QListWidget()
        for svc in services_mod.load_services():
            label = services_mod.service_label(svc)
            if not services_mod.is_ready(svc):
                label += "  ⚠ (URL)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, svc)
            self.svc_list.addItem(item)
        lay.addWidget(self.svc_list, 1)

        row = QHBoxLayout()
        btn_add = QPushButton(_tr("add_service"))
        btn_add.clicked.connect(self._on_add_service)
        btn_edit = QPushButton(_tr("edit_config"))
        btn_edit.clicked.connect(lambda: self._open_path(services_mod.SERVICES_FILE))
        row.addWidget(btn_add)
        row.addWidget(btn_edit)
        lay.addLayout(row)
        return w

    def _on_add_service(self):
        item = self.svc_list.currentItem()
        if not item:
            return
        svc = item.data(Qt.UserRole)
        layer, err = services_mod.add_service(svc)
        if err:
            return self._msg(err, Qgis.Warning)
        self._msg(f"{_tr('done')}: {services_mod.service_label(svc)}")

    # ------------------------------------------------------------ Data tab #
    def _tab_data(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        gb_db = QGroupBox(_tr("import_db"))
        dbl = QVBoxLayout(gb_db)
        row = QHBoxLayout()
        self.db_path = QLineEdit()
        btn_file = QPushButton("file…")
        btn_dir = QPushButton(".gdb…")
        btn_file.clicked.connect(self._pick_db_file)
        btn_dir.clicked.connect(self._pick_db_dir)
        row.addWidget(self.db_path, 1)
        row.addWidget(btn_file)
        row.addWidget(btn_dir)
        dbl.addLayout(row)
        fr = QHBoxLayout()
        fr.addWidget(QLabel(_tr("group_field")))
        self.group_field = QLineEdit()
        self.group_field.setPlaceholderText("auto (cadastral code)")
        fr.addWidget(self.group_field, 1)
        dbl.addLayout(fr)
        btn_imp = QPushButton(_tr("import_db"))
        btn_imp.clicked.connect(self._on_import_db)
        dbl.addWidget(btn_imp)
        dbl.addWidget(self._hint(_tr("import_db_hint")))
        lay.addWidget(gb_db)

        gb_fonts = QGroupBox(_tr("download_fonts"))
        fl = QVBoxLayout(gb_fonts)
        drow, self.fonts_dir = self._dir_row("fonts_dir")
        fl.addLayout(drow)
        self.install_fonts_cb = QCheckBox(_tr("install_fonts"))
        fl.addWidget(self.install_fonts_cb)
        btn_repo_fonts = QPushButton("↧ " + _tr("download_fonts_repo"))
        btn_repo_fonts.clicked.connect(self._on_download_fonts_repo)
        fl.addWidget(btn_repo_fonts)
        btn_fonts = QPushButton(_tr("download_fonts"))
        btn_fonts.clicked.connect(self._on_download_fonts)
        fl.addWidget(btn_fonts)
        fl.addWidget(self._hint(_tr("fonts_hint")))
        lay.addWidget(gb_fonts)

        gb_docs = QGroupBox(_tr("docs_group"))
        dl = QVBoxLayout(gb_docs)
        drow2, self.docs_dir = self._dir_row("docs_dir")
        dl.addLayout(drow2)
        btn_docs = QPushButton("↧ " + _tr("download_docs_repo"))
        btn_docs.clicked.connect(self._on_download_docs_repo)
        dl.addWidget(btn_docs)
        dl.addWidget(self._hint(_tr("docs_hint")))
        lay.addWidget(gb_docs)

        lay.addStretch(1)
        return w

    def _pick_db_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, _tr("import_db"), "",
            "Spatial data (*.mdb *.gdb *.shp *.gpkg *.sqlite);;All files (*)")
        if f:
            self.db_path.setText(f)

    def _pick_db_dir(self):
        d = QFileDialog.getExistingDirectory(self, ".gdb")
        if d:
            self.db_path.setText(d)

    def _on_import_db(self):
        path = self.db_path.text().strip()
        if not path or not os.path.exists(path):
            return self._msg(_tr("error"), Qgis.Warning)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            summary = db_mod.import_grouped(path, self.group_field.text().strip() or None)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        n = sum(len(v) for v in summary.values())
        self._msg(f"{_tr('done')}: {len(summary)} layer(s), {n} region group(s).")

    def _on_download_fonts(self):
        out = self.fonts_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            saved, pages = fonts_mod.download_all(out)
            installed = 0
            if self.install_fonts_cb.isChecked() and saved:
                installed = fonts_mod.install_fonts_windows(saved)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        for name, url in pages:
            webbrowser.open(url)
        msg = f"{_tr('done')}: {len(saved)} file(s)"
        if installed:
            msg += f", installed {installed}"
        if pages:
            msg += f", {len(pages)} opened in browser"
        self._msg(msg)

    def _on_download_fonts_repo(self):
        out = self.fonts_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            saved = repo_mod.download_category("fonts", out)
            ttfs = [p for p in saved if p.lower().endswith((".ttf", ".otf"))]
            installed = 0
            if self.install_fonts_cb.isChecked() and ttfs:
                installed = fonts_mod.install_fonts_windows(ttfs)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        msg = f"{_tr('done')}: {len(ttfs)} font(s)"
        if installed:
            msg += f", installed {installed}"
        self._msg(msg)

    def _on_download_docs_repo(self):
        out = self.docs_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            saved = repo_mod.download_category("docs", out)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._msg(f"{_tr('done')}: {len(saved)} file(s) → {out}")
        self._open_path(out)

    # ---------------------------------------------------------- Layout tab #
    def _tab_layout(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(50, 100000)
        self.scale_spin.setSingleStep(50)
        self.scale_spin.setValue(1000)
        form.addRow(_tr("map_scale"), self.scale_spin)
        lay.addLayout(form)

        btn_build = QPushButton(_tr("build_layout"))
        btn_build.clicked.connect(self._on_build_layout)
        lay.addWidget(btn_build)
        lay.addWidget(self._hint(_tr("build_layout_hint")))

        btn_open = QPushButton(_tr("open_layout"))
        btn_open.clicked.connect(self._on_open_layout)
        lay.addWidget(btn_open)
        lay.addStretch(1)
        return w

    def _on_build_layout(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layout_mod.build_layout(scale=self.scale_spin.value())
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        self._on_open_layout()
        self._msg(_tr("done"))

    def _on_open_layout(self):
        layout = QgsProject.instance().layoutManager().layoutByName(layout_mod.LAYOUT_NAME)
        if layout:
            self.iface.openLayoutDesigner(layout)

    # ------------------------------------------------------ Attachment tab #
    def _tab_attachment(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.survey_date = QDateEdit(QDate.currentDate())
        self.survey_date.setCalendarPopup(True)
        self.survey_date.setDisplayFormat("dd.MM.yyyy")
        form.addRow(_tr("survey_date"), self.survey_date)

        self.category_combo = QComboBox()
        self.category_combo.addItems(config.OPTIONS["category"])
        form.addRow(_tr("category"), self.category_combo)

        self.designation_combo = QComboBox()
        self.designation_combo.setEditable(True)
        self.designation_combo.addItems(config.OPTIONS["designation"])
        form.addRow(_tr("designation"), self.designation_combo)

        self.method_combo = QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.addItems(config.OPTIONS["method"])
        form.addRow(_tr("method"), self.method_combo)
        lay.addLayout(form)

        # Buildings table
        lay.addWidget(QLabel(_tr("buildings")))
        self.bld_table = QTableWidget(0, 5)
        self.bld_table.setHorizontalHeaderLabels(
            ["N", "დანიშ.", "მდგომ.", "სართ.", "ფართ."])
        lay.addWidget(self.bld_table)
        brow = QHBoxLayout()
        btn_load = QPushButton("↧ shenoba")
        btn_load.clicked.connect(self._load_buildings)
        btn_addrow = QPushButton("+")
        btn_addrow.clicked.connect(lambda: self.bld_table.insertRow(self.bld_table.rowCount()))
        brow.addWidget(btn_load)
        brow.addWidget(btn_addrow)
        brow.addStretch(1)
        lay.addLayout(brow)

        # Actions
        arow = QHBoxLayout()
        btn_xls = QPushButton(_tr("export_excel"))
        btn_xls.clicked.connect(self._on_write_excel)
        btn_photos = QPushButton(_tr("add_photos"))
        btn_photos.clicked.connect(self._on_pick_photos)
        arow.addWidget(btn_xls)
        arow.addWidget(btn_photos)
        lay.addLayout(arow)
        self.photos_label = QLabel("—")
        lay.addWidget(self.photos_label)
        self._photos = []

        btn_pkg = QPushButton("★ " + _tr("generate_package"))
        btn_pkg.clicked.connect(self._on_package)
        lay.addWidget(btn_pkg)
        lay.addWidget(self._hint(_tr("package_hint")))
        return w

    def _load_buildings(self):
        data = excel_mod.gather_from_project()
        self.bld_table.setRowCount(0)
        for b in data.get("buildings", []):
            r = self.bld_table.rowCount()
            self.bld_table.insertRow(r)
            for c, key in enumerate(["num", "func", "state", "floors", "area"]):
                self.bld_table.setItem(r, c, QTableWidgetItem(str(b.get(key, ""))))

    def _collect_form_data(self):
        data = excel_mod.gather_from_project()
        data["survey_date"] = self.survey_date.date().toString("dd.MM.yyyy")
        data["designation"] = self.designation_combo.currentText() or data.get("designation")
        data["method"] = self.method_combo.currentText()
        # buildings from the table override the auto-gathered ones
        buildings = []
        for r in range(self.bld_table.rowCount()):
            def cell(c):
                it = self.bld_table.item(r, c)
                return it.text() if it else ""
            if any(cell(c) for c in range(5)):
                buildings.append({"num": cell(0), "func": cell(1),
                                  "state": cell(2), "floors": cell(3), "area": cell(4)})
        if buildings:
            data["buildings"] = buildings
        return data

    def _on_write_excel(self):
        if not excel_mod.openpyxl_available():
            return self._openpyxl_hint()
        out = self.work_dir.text().strip() or self._settings.value(
            f"{config.SETTINGS_GROUP}/work_dir", "")
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        path = os.path.join(out, "danarti.xlsx")
        try:
            excel_mod.write_attachment(path, self._collect_form_data())
        except Exception as exc:  # noqa: BLE001
            return self._error(exc)
        self._msg(f"{_tr('done')}: {path}")

    def _on_pick_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, _tr("add_photos"), "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff)")
        if files:
            self._photos = files
            self.photos_label.setText(f"{len(files)} " + _tr("add_photos"))

    def _on_package(self):
        out = self._settings.value(f"{config.SETTINGS_GROUP}/work_dir", "")
        if hasattr(self, "work_dir") and self.work_dir.text().strip():
            out = self.work_dir.text().strip()
        if not out:
            return self._msg(_tr("pick_dir_first"), Qgis.Warning)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            folder, warnings = export_mod.package(
                out, photos=self._photos, excel_data=self._collect_form_data(),
                scale=getattr(self, "scale_spin", None).value() if hasattr(self, "scale_spin") else 1000)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            return self._error(exc)
        QApplication.restoreOverrideCursor()
        lvl = Qgis.Warning if warnings else Qgis.Success
        self._msg(f"{_tr('done')}: {folder}" + (f"  ({'; '.join(warnings)})" if warnings else ""), lvl)
        self._open_path(folder)

    # --------------------------------------------------------- Settings tab #
    def _tab_settings(self):
        w = QWidget()
        form = QFormLayout(w)
        g = config.SETTINGS_GROUP
        self.set_legal = QLineEdit(self._settings.value(f"{g}/auth_legal", ""))
        self.set_id = QLineEdit(self._settings.value(f"{g}/auth_id", ""))
        self.set_contact = QLineEdit(self._settings.value(f"{g}/auth_contact", ""))
        self.set_person = QLineEdit(self._settings.value(f"{g}/auth_person", ""))
        form.addRow(_tr("auth_legal"), self.set_legal)
        form.addRow(_tr("auth_id"), self.set_id)
        form.addRow(_tr("auth_contact"), self.set_contact)
        form.addRow(_tr("auth_person"), self.set_person)
        btn = QPushButton(_tr("save"))
        btn.clicked.connect(self._save_settings)
        form.addRow(btn)
        return w

    def _save_settings(self):
        g = config.SETTINGS_GROUP
        self._settings.setValue(f"{g}/auth_legal", self.set_legal.text())
        self._settings.setValue(f"{g}/auth_id", self.set_id.text())
        self._settings.setValue(f"{g}/auth_contact", self.set_contact.text())
        self._settings.setValue(f"{g}/auth_person", self.set_person.text())
        self._msg(_tr("done"))

    # -------------------------------------------------------------- helpers #
    @staticmethod
    def _wrap(layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    @staticmethod
    def _hint(text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: gray; font-size: 11px;")
        return lbl

    def _open_path(self, path):
        try:
            os.startfile(path)  # noqa: S606 - Windows only, user-triggered
        except (AttributeError, OSError):
            webbrowser.open("file://" + path)

    def _openpyxl_hint(self):
        QMessageBox.information(
            self, _tr("plugin_title"),
            "openpyxl არ არის დაყენებული / not installed.\n\n"
            "QGIS OSGeo4W Shell:\n    python -m pip install openpyxl")

    def _error(self, exc):
        self._msg(f"{_tr('error')}: {exc}", Qgis.Critical)
