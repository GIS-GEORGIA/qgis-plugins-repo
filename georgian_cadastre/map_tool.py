# -*- coding: utf-8 -*-
"""Map tool for reverse lookup: click the canvas -> emit a WGS84 point."""
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import pyqtSignal

_WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


class ParcelClickTool(QgsMapToolEmitPoint):
    """Emits ``pointClicked(lon, lat)`` in EPSG:4326 for each left click."""

    pointClicked = pyqtSignal(float, float)

    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas = canvas

    def canvasReleaseEvent(self, event):
        pt = self.toMapCoordinates(event.pos())
        map_crs = self._canvas.mapSettings().destinationCrs()
        if map_crs != _WGS84:
            tr = QgsCoordinateTransform(map_crs, _WGS84, QgsProject.instance())
            pt = tr.transform(pt)
        self.pointClicked.emit(pt.x(), pt.y())
