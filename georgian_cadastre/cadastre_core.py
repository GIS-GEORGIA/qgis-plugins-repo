# -*- coding: utf-8 -*-
"""QGIS glue: WKT (EPSG:4326) -> reprojected layer, and export to SHP/DXF/CSV.

This is the "last mile" only. All heavy lifting (CRS transforms, format
writers, area measurement) is QGIS core — we never reimplement it.
"""
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")

# UTM zones used across Georgia. maps.gov.ge offers exactly these two.
ZONE_37N = 32637  # 36°E – 42°E  (western Georgia)
ZONE_38N = 32638  # 42°E – 48°E  (eastern Georgia)

# Output CRS choices offered in the UI. (epsg, label-key handled by i18n/UI.)
CRS_CHOICES = [
    ("UTM 38N", ZONE_38N),
    ("UTM 37N", ZONE_37N),
    ("WGS84 (lat/lon)", 4326),
    ("Web Mercator", 3857),
]


def auto_zone_epsg(geom_wgs84):
    """Pick UTM 37N/38N from the parcel's centroid longitude (42°E boundary)."""
    c = geom_wgs84.centroid().asPoint()
    return ZONE_38N if c.x() >= 42.0 else ZONE_37N


def geometry_from_wkt(wkt):
    """Parse a WKT string into a QgsGeometry (assumed EPSG:4326)."""
    geom = QgsGeometry.fromWkt(wkt)
    if geom is None or geom.isEmpty():
        raise ValueError("Could not parse geometry WKT.")
    return geom


def _crs(epsg):
    return QgsCoordinateReferenceSystem("EPSG:{}".format(int(epsg)))


def _transform(geom_wgs84, target_epsg):
    """Return a copy of the geometry transformed from WGS84 to target_epsg."""
    if int(target_epsg) == 4326:
        return QgsGeometry(geom_wgs84)
    tr = QgsCoordinateTransform(WGS84, _crs(target_epsg), QgsProject.instance())
    g = QgsGeometry(geom_wgs84)
    g.transform(tr)
    return g


def true_area_perimeter(geom_wgs84):
    """True ground area (m²) and perimeter (m), independent of the output CRS.

    Always measured in the parcel's UTM zone, so ``area_m2`` stays correct even
    when the layer is exported in WGS84 or Web Mercator (where planar area is
    distorted)."""
    zone = auto_zone_epsg(geom_wgs84)
    g = _transform(geom_wgs84, zone)
    return g.area(), g.length()


def _fields():
    f = QgsFields()
    f.append(QgsField("cad_code", QVariant.String))
    f.append(QgsField("address", QVariant.String))
    f.append(QgsField("area_m2", QVariant.Double))     # computed in QGIS
    f.append(QgsField("perim_m", QVariant.Double))     # computed in QGIS
    f.append(QgsField("area_off", QVariant.Double))    # official (maps.gov.ge)
    f.append(QgsField("type", QVariant.String))
    f.append(QgsField("status", QVariant.String))
    f.append(QgsField("source", QVariant.String))
    return f


def build_layer(features, code, address, target_epsg, info=None):
    """Create an in-memory MultiPolygon layer in the target CRS.

    ``features`` is the list returned by napr_client.fetch_features (each has
    ``wkt`` in EPSG:4326). ``info`` is the optional non-personal attribute dict
    from napr_client.fetch_info.
    """
    info = info or {}
    crs = _crs(target_epsg)
    layer = QgsVectorLayer(
        "MultiPolygon?crs={}".format(crs.authid()), code or "parcel", "memory"
    )
    dp = layer.dataProvider()
    dp.addAttributes(_fields().toList())
    layer.updateFields()

    for feat_row in features:
        geom4326 = geometry_from_wkt(feat_row["wkt"])
        geom = _transform(geom4326, target_epsg)
        area, perim = true_area_perimeter(geom4326)
        f = QgsFeature(layer.fields())
        f.setGeometry(geom)
        f.setAttributes([
            feat_row.get("code") or code,
            address,
            round(area, 2),
            round(perim, 2),
            info.get("area_official"),
            info.get("parcel_type", ""),
            info.get("status", ""),
            "maps.gov.ge",
        ])
        dp.addFeature(f)

    layer.updateExtents()
    return layer


def add_to_project(layer):
    QgsProject.instance().addMapLayer(layer)
    return layer


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
_DRIVERS = {"SHP": "ESRI Shapefile", "DXF": "DXF"}


def _geometry_only_clone(layer):
    """A copy of `layer` with same CRS and geometries but no attribute fields.
    The OGR DXF writer rejects arbitrary fields; CAD output is geometry anyway.
    """
    wkb = QgsWkbTypes.displayString(layer.wkbType())
    clone = QgsVectorLayer(
        "{}?crs={}".format(wkb, layer.crs().authid()), layer.name(), "memory"
    )
    dp = clone.dataProvider()
    for src in layer.getFeatures():
        f = QgsFeature()
        f.setGeometry(src.geometry())
        dp.addFeature(f)
    clone.updateExtents()
    return clone


def export_layer(layer, fmt, path):
    """Write `layer` to `path` as SHP or DXF. Returns "" on success, else the
    raw driver message (the caller localizes the prefix)."""
    fmt = fmt.upper()
    driver = _DRIVERS.get(fmt)
    if driver is None:
        raise ValueError("Unsupported format: {}".format(fmt))

    if fmt == "DXF":
        layer = _geometry_only_clone(layer)

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = driver
    opts.fileEncoding = "UTF-8"

    ctx = QgsProject.instance().transformContext() \
        if hasattr(QgsProject.instance(), "transformContext") \
        else QgsCoordinateTransformContext()

    err = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, ctx, opts)
    code = err[0] if isinstance(err, (tuple, list)) else err
    if code != QgsVectorFileWriter.NoError:
        return err[1] if isinstance(err, (tuple, list)) and len(err) > 1 else "?"
    return ""


def export_csv_vertices(layer, path, decimals=3):
    """Export polygon vertices as CSV (part,id,X,Y) in the layer's CRS.

    Matches webgis.ge's CSV (a plain vertex coordinate list). A ``part`` column
    keeps multi-feature / multi-part parcels separable.
    """
    feats = list(layer.getFeatures())
    if not feats:
        return "err_empty_layer"

    fmt = u"{{:.{}f}}".format(decimals)
    lines = ["part,id,X,Y"]
    part = 1
    for feat in feats:
        geom = feat.geometry()
        rings = []
        if geom.isMultipart():
            for poly in geom.asMultiPolygon():
                rings.extend(poly)
        else:
            rings.extend(geom.asPolygon())
        for ring in rings:
            n = 1
            for pt in ring:
                lines.append(u"{},{},{},{}".format(
                    part, n, fmt.format(pt.x()), fmt.format(pt.y())))
                n += 1
            part += 1

    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(u"\n".join(lines))
    except OSError as exc:
        return str(exc)
    return ""
