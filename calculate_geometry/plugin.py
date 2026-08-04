# -*- coding: utf-8 -*-
"""Plugin bootstrap: adds a 'Calculate Geometry…' action to the Vector menu/toolbar.

POC — untested.
"""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsVectorLayer

from .calculate_geometry_dialog import CalculateGeometryDialog


class CalculateGeometryPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self._dir = os.path.dirname(__file__)

    def initGui(self):  # noqa: N802 (QGIS-required name)
        icon_path = os.path.join(self._dir, "icon.svg")
        self.action = QAction(
            QIcon(icon_path), "Calculate Geometry…", self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu("Calculate Geometry", self.action)
        self.iface.addVectorToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginVectorMenu("Calculate Geometry", self.action)
            self.iface.removeVectorToolBarIcon(self.action)
            self.action = None

    def run(self):
        # Pre-select the active layer if it's a vector layer; otherwise the
        # dialog's own layer combo / Browse button lets the user pick one.
        active = self.iface.activeLayer()
        layer = active if isinstance(active, QgsVectorLayer) else None
        dlg = CalculateGeometryDialog(layer, self.iface, self.iface.mainWindow())
        dlg.exec_()
