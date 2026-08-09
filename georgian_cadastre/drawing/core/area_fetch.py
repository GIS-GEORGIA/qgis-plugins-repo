# -*- coding: utf-8 -*-
"""Bulk parcel download over an *area* — a radius around a cadastral code, or
the current map extent — as a cancellable/pausable background task.

Strategy: sample a grid of points across the target area, reverse-lookup each
point on maps.gov.ge/NAPR (proxy-aware, off the GUI thread), union the results
by parcel, then fetch each unique parcel's geometry. Progress is reported the
whole way so the UI never appears frozen.
"""

import time

from qgis.core import (
    QgsTask,
    QgsGeometry,
    QgsFeature,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)

from . import config
from . import crs as crs_mod
from . import styles as styles_mod
from . import templates as tpl_mod
from ... import napr_client
from ...qgis_net import qgis_fetch

WGS84 = "EPSG:4326"

# Safety cap so an over-large area can't spawn thousands of requests silently.
MAX_POINTS = 500


# --------------------------------------------------------------------------- #
# Grid helpers (pure, projected metres) — testable without QGIS GUI.
# --------------------------------------------------------------------------- #
def extent_grid(xmin, ymin, xmax, ymax, step):
    """Grid of (x, y) points covering an extent, spacing = step (metres)."""
    step = max(float(step), 1.0)
    pts = []
    y = ymin
    while y <= ymax + 1e-6:
        x = xmin
        while x <= xmax + 1e-6:
            pts.append((x, y))
            x += step
        y += step
    return pts


def circle_grid(cx, cy, radius, step):
    """Grid of (x, y) points inside a circle (centre cx,cy, radius m)."""
    step = max(float(step), 1.0)
    pts = [(cx, cy)]
    r2 = radius * radius
    y = cy - radius
    while y <= cy + radius + 1e-6:
        x = cx - radius
        while x <= cx + radius + 1e-6:
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                pts.append((x, y))
            x += step
        y += step
    return pts


def cap_points(points):
    """Return (points, dropped) after applying MAX_POINTS by even sampling."""
    n = len(points)
    if n <= MAX_POINTS:
        return points, 0
    keep_every = n / float(MAX_POINTS)
    sampled = [points[int(i * keep_every)] for i in range(MAX_POINTS)]
    return sampled, n - len(sampled)


# --------------------------------------------------------------------------- #
# Result layer
# --------------------------------------------------------------------------- #
def ensure_parcels_layer(project, zone, name="napr_parcels"):
    """A dedicated bulk-results layer (kept separate from the drawing nakveti)."""
    from .styles import normalise
    for layer in project.mapLayers().values():
        if hasattr(layer, "getFeatures") and layer.name() == name:
            return layer
    crs = crs_mod.zone_crs(zone)
    layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", name, "memory")
    fields = tpl_mod._fields_for(config.LAYER_SCHEMAS["nakveti"])
    layer.dataProvider().addAttributes(fields.toList())
    layer.updateFields()
    project.addMapLayer(layer)
    styles_mod.apply_style(layer)   # 'nakveti'-style outline+area label
    return layer


def add_parcels(project, zone, parcels, name="napr_parcels"):
    """Add fetched parcels (list of {code,address,wkt,epsg}) to the layer.

    Skips duplicates already present (by LEGAL_DOC). Returns (added, layer).
    """
    layer = ensure_parcels_layer(project, zone, name)
    dst = crs_mod.zone_crs(zone)
    names = layer.fields().names()
    existing = set()
    if "LEGAL_DOC" in names:
        idx = layer.fields().indexOf("LEGAL_DOC")
        existing = set(layer.uniqueValues(idx))

    feats = []
    added_codes = set()
    for p in parcels:
        code = p.get("code", "")
        if code and (code in existing or code in added_codes):
            continue
        geom = QgsGeometry.fromWkt(p["wkt"])
        if geom is None or geom.isEmpty():
            continue
        src = QgsCoordinateReferenceSystem(p.get("epsg") or WGS84)
        if src != dst:
            geom.transform(QgsCoordinateTransform(src, dst, project))
        f = QgsFeature(layer.fields())
        f.setGeometry(geom)
        if "LEGAL_DOC" in names:
            f["LEGAL_DOC"] = code
        if "ADDRESS" in names:
            f["ADDRESS"] = p.get("address", "")
        if "Shape_Area" in names:
            f["Shape_Area"] = round(crs_mod.polygon_area_m2(geom, dst), 2)
        feats.append(f)
        added_codes.add(code)
    if feats:
        layer.dataProvider().addFeatures(feats)
        layer.updateExtents()
        layer.triggerRepaint()
    return len(feats), layer


# --------------------------------------------------------------------------- #
# The background task
# --------------------------------------------------------------------------- #
class AreaFetchTask(QgsTask):
    """Reverse-lookup a set of WGS84 points, then fetch each unique parcel.

    ``points`` is a list of (lon, lat) in EPSG:4326. ``result`` ends up a list
    of {code, address, wkt, epsg}. Cancel via the standard QgsTask cancel;
    pause/resume via pause()/resume().
    """

    def __init__(self, points, per_radius, limit=15):
        super().__init__("Georgian Cadastre: area fetch", QgsTask.CanCancel)
        self._points = points
        self._per_radius = per_radius
        self._limit = limit
        self._paused = False
        self.result = []
        self.error = None
        self.stats = {"points": len(points), "parcels": 0}

    # pause/resume (checked from the worker loop) --------------------------
    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def is_paused(self):
        return self._paused

    def _blocked(self):
        """Sleep while paused; return True if cancelled meanwhile."""
        while self._paused and not self.isCanceled():
            time.sleep(0.12)
        return self.isCanceled()

    def run(self):  # worker thread
        try:
            seen = {}
            npts = len(self._points) or 1
            for i, (lon, lat) in enumerate(self._points):
                if self._blocked():
                    return False
                try:
                    matches = napr_client.reverse(
                        lon, lat, radius=self._per_radius, limit=self._limit,
                        fetch=qgis_fetch)
                except Exception:  # noqa: BLE001 — one bad point shouldn't stop all
                    matches = []
                for m in matches:
                    seen.setdefault(m["lbl"], m)
                self.setProgress(60.0 * (i + 1) / npts)

            matches = list(seen.values())
            self.stats["parcels"] = len(matches)
            nl = len(matches) or 1
            for j, m in enumerate(matches):
                if self._blocked():
                    return False
                try:
                    feats = napr_client.fetch_features(m["lbl"], fetch=qgis_fetch)
                    for f in feats:
                        self.result.append({
                            "code": m.get("code", ""),
                            "address": m.get("address", ""),
                            "wkt": f["wkt"], "epsg": f["epsg"],
                        })
                except Exception:  # noqa: BLE001
                    pass
                self.setProgress(60.0 + 40.0 * (j + 1) / nl)
            return True
        except Exception as exc:  # noqa: BLE001
            self.error = exc
            return False
