# -*- coding: utf-8 -*-
"""CRS helpers for UTM zones 37N / 38N."""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsDistanceArea,
    QgsGeometry,
    QgsUnitTypes,
)

from . import config


def zone_crs(zone):
    """Return a QgsCoordinateReferenceSystem for zone 37 or 38."""
    epsg = config.ZONES.get(int(zone), config.ZONES[config.DEFAULT_ZONE])
    return QgsCoordinateReferenceSystem(epsg)


def zone_for_longitude(lon):
    """Pick the natural UTM zone (37 or 38) for a WGS84 longitude."""
    return 37 if lon < 42.0 else 38


def set_project_crs(zone):
    QgsProject.instance().setCrs(zone_crs(zone))


def polygon_area_m2(geometry, layer_crs, zone=None):
    """True planimetric area (m²) of a geometry.

    Measured with QgsDistanceArea on the ellipsoid so the value is correct
    regardless of the layer's CRS — matches how NAPR reports official areas.
    """
    da = QgsDistanceArea()
    da.setSourceCrs(layer_crs, QgsProject.instance().transformContext())
    da.setEllipsoid(QgsProject.instance().ellipsoid() or "WGS84")
    area = da.measureArea(geometry)
    return da.convertAreaMeasurement(area, QgsUnitTypes.AreaSquareMeters)


def transform(geometry, src_crs, dst_crs):
    tr = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
    g = QgsGeometry(geometry)
    g.transform(tr)
    return g
