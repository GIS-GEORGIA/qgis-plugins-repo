# -*- coding: utf-8 -*-
"""Drop a NAPR parcel (fetched by cadastral code or map click) into the
drawing's ``nakveti`` layer.

Reuses the plugin's existing NAPR client (code → WKT in EPSG:4326); this module
only handles the QGIS side: reproject to the chosen UTM zone, create the
nakveti layer if it is missing, and append the parcel with its code, address
and computed area.
"""

from qgis.core import (
    QgsGeometry,
    QgsFeature,
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)

from . import config
from . import crs as crs_mod
from . import styles as styles_mod
from . import templates as tpl_mod

WGS84 = "EPSG:4326"


def find_nakveti(project):
    for layer in project.mapLayers().values():
        if hasattr(layer, "getFeatures") and \
                styles_mod.normalise(layer.name()) == "nakveti":
            return layer
    return None


def ensure_nakveti(project, zone):
    """Return the nakveti layer, creating an in-memory one if none exists."""
    layer = find_nakveti(project)
    if layer is not None:
        return layer
    crs = crs_mod.zone_crs(zone)
    layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "nakveti", "memory")
    fields = tpl_mod._fields_for(config.LAYER_SCHEMAS["nakveti"])
    layer.dataProvider().addAttributes(fields.toList())
    layer.updateFields()
    project.addMapLayer(layer)
    styles_mod.apply_style(layer)
    return layer


def add_parcel(project, zone, wkt, code="", address="", src_epsg=WGS84):
    """Insert one parcel geometry into nakveti. Returns (area_m2, layer)."""
    geom = QgsGeometry.fromWkt(wkt)
    if geom is None or geom.isEmpty():
        raise ValueError("empty geometry")
    src = QgsCoordinateReferenceSystem(src_epsg)
    dst = crs_mod.zone_crs(zone)
    if src != dst:
        geom.transform(QgsCoordinateTransform(src, dst, project))

    layer = ensure_nakveti(project, zone)
    area = crs_mod.polygon_area_m2(geom, dst)

    feat = QgsFeature(layer.fields())
    feat.setGeometry(geom)
    names = layer.fields().names()
    if "LEGAL_DOC" in names:
        feat["LEGAL_DOC"] = code
    if "ADDRESS" in names:
        feat["ADDRESS"] = address
    if "Shape_Area" in names:
        feat["Shape_Area"] = round(area, 2)
    layer.dataProvider().addFeatures([feat])
    layer.updateExtents()
    layer.triggerRepaint()
    return area, layer
