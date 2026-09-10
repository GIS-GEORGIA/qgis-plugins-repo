# -*- coding: utf-8 -*-
"""
Selection Tools — ArcGIS Pro-ს "Selection" submenu-ს ანალოგი QGIS-ში.

ფენების პანელში ვექტორულ შრეზე მარჯვენა-კლიკზე ჩნდება ქვემენიუ
„მონიშვნა / Selection" ArcGIS Pro-ს იგივე ხელსაწყოებით. ვარსკვლავი —
„შრის შექმნა მონიშნულებიდან" (Make Layer From Selected Features).

Attribution:
  ბირთვის იდეა (clone + setSubsetString) ეფუძნება Murat Çalışkan-ის
  "Create Layer From Selected Features" პლაგინს (GPLv2+).
  იხ. NOTICE.md. აქ ის გადაკეთდა და გაუმჯობესდა Giorgi Kapanadze-ს მიერ:
  PostGIS/FileGDB-ის PK-ის სწორი დამუშავება, ორენოვანი UI, ArcGIS-სტილის
  submenu დამატებითი ხელსაწყოებით.
"""
from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.core import (
    QgsProject,
    QgsFeatureRequest,
    QgsCoordinateTransform,
    Qgis,
)

from .selection_ops import (
    make_layer_from_selection,
    apply_definition_query_from_selection,
    add_autoincrement_key,
)
from . import i18n

_DIR = os.path.dirname(os.path.abspath(__file__))


def _vector_layer_type():
    """QgsMapLayerType.VectorLayer / Qgis.LayerType.Vector — cross-version."""
    try:
        from qgis.core import Qgis as _Q
        return _Q.LayerType.Vector
    except Exception:
        pass
    from qgis.core import QgsMapLayerType
    return QgsMapLayerType.VectorLayer


class SelectionToolsPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.lang = i18n.DEFAULT_LANG
        self.menu = None          # QMenu — ჩადგმული "Selection ▸"
        self.root_action = None   # QAction, რომელსაც ეს menu ეკიდება
        self._added_to_layer_menu = False
        self._icon = QIcon(os.path.join(_DIR, "icon.svg"))

    # ---- lifecycle -------------------------------------------------------
    def initGui(self):
        self.lang = i18n.resolve_lang()

        # ArcGIS Pro-ს "Selection"-ის თანმიმდევრობა; None = გამყოფი
        items = [
            ("zoom_to", self.zoom_to),
            ("pan_to", self.pan_to),
            None,
            ("clear", self.clear_selection),
            ("switch", self.switch_selection),
            ("select_all", self.select_all),
            ("select_visible", self.select_visible),
            None,
            ("def_query", self.def_query),
            ("make_layer", self.make_layer),
            None,
            ("attr_table", self.attr_table),
        ]

        # ჩადგმული ქვემენიუ — ArcGIS-ის იდენტური "Selection ▸"
        self.menu = QMenu(i18n.t("selection", self.lang))
        self.menu.setIcon(self._icon)
        for entry in items:
            if entry is None:
                self.menu.addSeparator()
                continue
            key, cb = entry
            act = self.menu.addAction(i18n.t(key, self.lang))
            if key == "make_layer":
                act.setIcon(self._icon)  # ვარსკვლავს — ხატულა
            act.triggered.connect(cb)

        # root action, რომელსაც ქვემენიუ ჰკიდია — Qt ავტომატურად აჩვენებს ▸-ს
        self.root_action = QAction(self._icon, i18n.t("selection", self.lang),
                                   self.iface.mainWindow())
        self.root_action.setMenu(self.menu)

        # (1) შრის კონტექსტური მენიუ — მთავარი ადგილი
        ltype = _vector_layer_type()
        try:
            self.iface.addCustomActionForLayerType(
                self.root_action, "", ltype, True)
        except Exception:
            pass

        # (2) აღმოჩენადობისთვის — Vector მენიუშიც
        try:
            self.iface.addPluginToVectorMenu(i18n.t("title", self.lang),
                                             self.root_action)
            self._added_to_layer_menu = True
        except Exception:
            self._added_to_layer_menu = False

    def unload(self):
        if self.root_action is not None:
            try:
                self.iface.removeCustomActionForLayerType(self.root_action)
            except Exception:
                pass
            if self._added_to_layer_menu:
                try:
                    self.iface.removePluginVectorMenu(
                        i18n.t("title", self.lang), self.root_action)
                except Exception:
                    pass
        self.root_action = None
        self.menu = None

    # ---- helpers ---------------------------------------------------------
    def _target_layers(self):
        """მოქმედების სამიზნე ვექტორული შრეები (ხე-პანელში მონიშნული → active)."""
        layers = []
        try:
            layers = [l for l in self.iface.layerTreeView().selectedLayers()
                      if l is not None and l.type() == 0]  # 0 = VectorLayer
        except Exception:
            pass
        if not layers:
            act = self.iface.activeLayer()
            if act is not None and act.type() == 0:
                layers = [act]
        return layers

    def _msg(self, text, level=Qgis.Info, secs=5):
        self.iface.messageBar().pushMessage(
            i18n.t("title", self.lang), text, level=level, duration=secs)

    def _warn_no_layer(self):
        self._msg(i18n.t("no_layer", self.lang), Qgis.Warning)

    def _offer_autokey(self, lyr):
        """ცარიელი შედეგისას სთავაზობს ავტო-ინკრემენტ ველის დამატებას.
        :returns: True თუ ველი დაემატა და ღირს ხელახლა ცდა."""
        from qgis.PyQt.QtWidgets import QMessageBox
        if lyr.isEditable():
            self._msg(i18n.t("autokey_editing", self.lang), Qgis.Warning, 8)
            return False
        ans = QMessageBox.question(
            self.iface.mainWindow(), i18n.t("title", self.lang),
            i18n.t("offer_autokey", self.lang, name=lyr.name()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ans != QMessageBox.StandardButton.Yes:
            return False
        sel = lyr.selectedFeatureIds()          # შევინახოთ მონიშვნა
        field, status = add_autoincrement_key(lyr)
        if status != "ok":
            key = "autokey_editing" if status == "editing" else "autokey_failed"
            self._msg(i18n.t(key, self.lang, reason=status), Qgis.Critical, 8)
            return False
        lyr.selectByIds(sel)                     # აღვადგინოთ მონიშვნა
        self._msg(i18n.t("autokey_added", self.lang, field=field))
        return True

    # ---- ArcGIS-style tools ---------------------------------------------
    def zoom_to(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        canvas = self.iface.mapCanvas()
        try:
            canvas.zoomToSelected(layers if len(layers) > 1 else layers[0])
        except Exception:
            canvas.zoomToSelected(layers[0])

    def pan_to(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        canvas = self.iface.mapCanvas()
        try:
            canvas.panToSelected(layers if len(layers) > 1 else layers[0])
        except Exception:
            canvas.panToSelected(layers[0])

    def clear_selection(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        for lyr in layers:
            lyr.removeSelection()

    def switch_selection(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        for lyr in layers:
            lyr.invertSelection()

    def select_all(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        for lyr in layers:
            lyr.selectAll()

    def select_visible(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        canvas = self.iface.mapCanvas()
        canvas_crs = canvas.mapSettings().destinationCrs()
        extent = canvas.extent()
        for lyr in layers:
            rect = extent
            try:
                if lyr.crs() != canvas_crs:
                    xform = QgsCoordinateTransform(
                        canvas_crs, lyr.crs(), QgsProject.instance())
                    rect = xform.transformBoundingBox(extent)
            except Exception:
                pass
            req = QgsFeatureRequest().setFilterRect(rect).setNoAttributes()
            ids = [f.id() for f in lyr.getFeatures(req)]
            lyr.selectByIds(ids)

    def def_query(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        for lyr in layers:
            status, n, subset = apply_definition_query_from_selection(lyr)
            if status == "empty" and self._offer_autokey(lyr):
                status, n, subset = apply_definition_query_from_selection(lyr)
            if status == "no_selection":
                self._msg(i18n.t("no_selection", self.lang), Qgis.Warning)
            elif status == "empty":
                self._msg(i18n.t("empty_result", self.lang, q=subset), Qgis.Critical, 10)
            else:
                self._msg(i18n.t("def_applied", self.lang, name=lyr.name(), n=n))

    def make_layer(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        made_any = False
        for lyr in layers:
            new, status, n, subset = make_layer_from_selection(lyr)
            if status == "empty" and self._offer_autokey(lyr):
                new, status, n, subset = make_layer_from_selection(lyr)
            if status == "no_selection":
                self._msg(i18n.t("no_selection", self.lang), Qgis.Warning)
            elif status == "empty":
                self._msg(i18n.t("empty_result", self.lang, q=subset), Qgis.Critical, 10)
            else:
                made_any = True
                self._msg(i18n.t("made_layer", self.lang, name=new.name(), n=n))
        return made_any

    def attr_table(self):
        layers = self._target_layers()
        if not layers:
            return self._warn_no_layer()
        for lyr in layers:
            # ცხრილს ვხსნით; მონიშნულებზე ფილტრი ცხრილშივე ერთ-კლიკიანია
            # (ქვედა ზოლში „Show Selected Features"). iface API filter-mode-ს
            # პირდაპირ არ აძლევს, ამიტომ უსაფრთხოდ ვხსნით შრეს.
            self.iface.showAttributeTable(lyr)
