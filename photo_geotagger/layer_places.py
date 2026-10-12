"""Place names from a QGIS layer: the attributes of the polygon that contains the photo,
or of the nearest point feature within a maximum distance. Needs QGIS."""
from qgis.core import (
    NULL, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsCsException, QgsGeometry, QgsPointXY,
    QgsRectangle, QgsSpatialIndex)

from . import core

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


def _text(value):
    return "" if value is None or value == NULL else str(value).strip()


class LayerLookup:
    """`features`: iterable of QgsFeature (layer.getFeatures() or a processing source).
    `mapping`: {"country": field name or "", "region": ..., "city": ..., "location": ...}."""

    def __init__(self, features, crs, mapping, transform_context, max_distance=100.0):
        self.mapping = {key: field for key, field in mapping.items() if field}
        self.max_distance = max_distance
        self.to_layer = QgsCoordinateTransform(WGS84, crs, transform_context)
        self.to_wgs = QgsCoordinateTransform(crs, WGS84, transform_context)
        self.geoms, self.attrs = {}, {}
        self.index = QgsSpatialIndex()
        for f in features:
            if f.geometry().isNull():
                continue
            self.geoms[f.id()] = QgsGeometry(f.geometry())
            self.attrs[f.id()] = {key: _text(f[field]) for key, field in self.mapping.items()}
            self.index.addFeature(f)

    def _place(self, fid):
        return {key: value for key, value in self.attrs[fid].items() if value}

    def lookup(self, lat, lon):
        """Place dict for the coordinates, or {} when nothing fits."""
        try:
            pt = self.to_layer.transform(QgsPointXY(lon, lat))
        except QgsCsException:
            return {}
        probe = QgsGeometry.fromPointXY(pt)
        for fid in self.index.intersects(QgsRectangle(pt, pt)):
            if self.geoms[fid].contains(probe):
                return self._place(fid)
        if self.max_distance > 0:
            for fid in self.index.nearestNeighbor(pt, 1):
                near = self.geoms[fid].nearestPoint(probe).asPoint()
                try:
                    p = self.to_wgs.transform(near)
                except QgsCsException:
                    continue
                if core._distance_m(lat, lon, p.y(), p.x()) <= self.max_distance:
                    return self._place(fid)
        return {}
