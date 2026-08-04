# -*- coding: utf-8 -*-
"""Compute geometry properties for a layer's features.

Mirrors the logic of core's QgsExportGeometryAttributesAlgorithm
(3 methods: Cartesian in layer CRS / Cartesian in a chosen CRS / Ellipsoidal)
so a future core version can share one code path.

POC — untested (no QGIS runtime available while authoring).
"""
from enum import Enum

from qgis.core import (
    QgsCoordinateTransform,
    QgsCsException,
    QgsDistanceArea,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsUnitTypes,
    QgsWkbTypes,
)


class Method(Enum):
    CARTESIAN_LAYER_CRS = 0   # measure in the layer's own CRS, planar
    CARTESIAN_TARGET_CRS = 1  # reproject to target CRS, then planar
    ELLIPSOIDAL = 2           # geodesic, using the project ellipsoid


# Each property: key -> (label, unit_kind, value_type)
#   unit_kind:  'distance' | 'area' | None
#   value_type: 'double' | 'int' | 'string'
POINT_PROPERTIES = {
    "x": ("Point x-coordinate", None, "double"),
    "y": ("Point y-coordinate", None, "double"),
    "xy_notation": ("Point x- and y-coordinate notation", None, "string"),
}
LINE_PROPERTIES = {
    "length": ("Length (geodesic)", "distance", "double"),
    "bearing": ("Line bearing", None, "double"),
    "numparts": ("Number of parts", None, "int"),
    "numvertices": ("Number of vertices", None, "int"),
    "numcurves": ("Number of curves", None, "int"),
    "start_x": ("Line start x-coordinate", None, "double"),
    "start_y": ("Line start y-coordinate", None, "double"),
    "end_x": ("Line end x-coordinate", None, "double"),
    "end_y": ("Line end y-coordinate", None, "double"),
    "centroid_x": ("Centroid x-coordinate", None, "double"),
    "centroid_y": ("Centroid y-coordinate", None, "double"),
    "central_x": ("Central point x-coordinate", None, "double"),
    "central_y": ("Central point y-coordinate", None, "double"),
}
POLYGON_PROPERTIES = {
    "area": ("Area (geodesic)", "area", "double"),
    "perimeter": ("Perimeter length (geodesic)", "distance", "double"),
    "numparts": ("Number of parts", None, "int"),
    "numvertices": ("Number of vertices", None, "int"),
    "numholes": ("Number of holes", None, "int"),
    "numcurves": ("Number of curves", None, "int"),
    "centroid_x": ("Centroid x-coordinate", None, "double"),
    "centroid_y": ("Centroid y-coordinate", None, "double"),
    "central_x": ("Central point x-coordinate", None, "double"),
    "central_y": ("Central point y-coordinate", None, "double"),
    "min_x": ("Minimum x-coordinate", None, "double"),
    "min_y": ("Minimum y-coordinate", None, "double"),
    "max_x": ("Maximum x-coordinate", None, "double"),
    "max_y": ("Maximum y-coordinate", None, "double"),
}


def properties_for_geometry(geometry_type):
    """Return the {key: (label, unit_kind, value_type)} dict for a geometry type."""
    if geometry_type == QgsWkbTypes.PointGeometry:
        return POINT_PROPERTIES
    if geometry_type == QgsWkbTypes.LineGeometry:
        return LINE_PROPERTIES
    if geometry_type == QgsWkbTypes.PolygonGeometry:
        return POLYGON_PROPERTIES
    return {}


def _entry(geometry_type, prop_key):
    return properties_for_geometry(geometry_type).get(prop_key)


def unit_kind_for_property(geometry_type, prop_key):
    e = _entry(geometry_type, prop_key)
    return e[1] if e else None


def value_type_for_property(geometry_type, prop_key):
    e = _entry(geometry_type, prop_key)
    return e[2] if e else "double"


def _first_last_points(geom):
    """First and last vertices of a geometry as QgsPoint, or (None, None)."""
    it = geom.vertices()
    try:
        first = next(it)
    except StopIteration:
        return None, None
    last = first
    for v in it:
        last = v
    return first, last


class GeometryCalculator:
    """Computes a single property value per feature, honouring method/CRS/unit."""

    def __init__(self, layer, method, target_crs, project=None):
        self.layer = layer
        self.method = method
        self.target_crs = target_crs
        self.project = project or QgsProject.instance()

        self._da = QgsDistanceArea()
        self._transform = None
        self._distance_factor = 1.0
        self._area_factor = 1.0

        tc = self.project.transformContext()
        source_crs = layer.crs()

        if method == Method.ELLIPSOIDAL:
            self._da.setSourceCrs(source_crs, tc)
            self._da.setEllipsoid(self.project.ellipsoid())
        elif method == Method.CARTESIAN_TARGET_CRS:
            self._transform = QgsCoordinateTransform(source_crs, target_crs, tc)
            self._da.setSourceCrs(target_crs, tc)
            self._da.setEllipsoid("NONE")  # planar in the target CRS
        else:  # CARTESIAN_LAYER_CRS
            self._da.setSourceCrs(source_crs, tc)
            self._da.setEllipsoid("NONE")

    def set_output_units(self, distance_unit=None, area_unit=None):
        if distance_unit is not None:
            self._distance_factor = QgsUnitTypes.fromUnitToUnitFactor(
                self._da.lengthUnits(), distance_unit
            )
        if area_unit is not None:
            self._area_factor = QgsUnitTypes.fromUnitToUnitFactor(
                self._da.areaUnits(), area_unit
            )

    def _prepared_geometry(self, geom):
        if self.method == Method.CARTESIAN_TARGET_CRS and self._transform is not None:
            geom = QgsGeometry(geom)  # copy before mutating
            try:
                geom.transform(self._transform)
            except QgsCsException:
                return None
        return geom

    def value(self, feature, prop_key):
        """Return the computed value of prop_key for a feature, or None."""
        geom = feature.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            return None
        geom = self._prepared_geometry(geom)
        if geom is None:
            return None

        g = geom.constGet()

        # --- point ---
        if prop_key in ("x", "y", "xy_notation"):
            try:
                p = geom.asPoint()
            except Exception:  # multipoint or unexpected type -> use centroid
                p = geom.centroid().asPoint()
            if prop_key == "x":
                return p.x()
            if prop_key == "y":
                return p.y()
            return "{}, {}".format(p.x(), p.y())

        # --- counts ---
        if prop_key == "numparts":
            return g.partCount()
        if prop_key == "numvertices":
            return g.nCoordinates()
        if prop_key == "numcurves":
            # POC best-effort: whether the geometry carries curved segments.
            # TODO: count individual circular/compound curve segments.
            return 1 if g.hasCurvedSegments() else 0
        if prop_key == "numholes":
            try:
                if geom.isMultipart():
                    return sum(g.geometryN(i).numInteriorRings()
                               for i in range(g.numGeometries()))
                return g.numInteriorRings()
            except AttributeError:
                return None

        # --- line endpoints / bearing ---
        if prop_key in ("start_x", "start_y", "end_x", "end_y", "bearing"):
            first, last = _first_last_points(geom)
            if first is None:
                return None
            if prop_key == "start_x":
                return first.x()
            if prop_key == "start_y":
                return first.y()
            if prop_key == "end_x":
                return last.x()
            if prop_key == "end_y":
                return last.y()
            return QgsPointXY(first).azimuth(QgsPointXY(last))  # degrees CW from N

        # --- measurements ---
        if prop_key == "length":
            return self._distance_factor * self._da.measureLength(geom)
        if prop_key == "perimeter":
            return self._distance_factor * self._da.measurePerimeter(geom)
        if prop_key == "area":
            return self._area_factor * self._da.measureArea(geom)

        # --- derived points ---
        if prop_key in ("centroid_x", "centroid_y"):
            c = geom.centroid().asPoint()
            return c.x() if prop_key == "centroid_x" else c.y()
        if prop_key in ("central_x", "central_y"):
            c = geom.pointOnSurface().asPoint()
            return c.x() if prop_key == "central_x" else c.y()

        # --- bounding box ---
        if prop_key in ("min_x", "min_y", "max_x", "max_y"):
            r = geom.boundingBox()
            return {
                "min_x": r.xMinimum(), "min_y": r.yMinimum(),
                "max_x": r.xMaximum(), "max_y": r.yMaximum(),
            }[prop_key]

        return None
