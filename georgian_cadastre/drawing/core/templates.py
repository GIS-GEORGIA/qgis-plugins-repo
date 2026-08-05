# -*- coding: utf-8 -*-
"""Create empty SHP templates from LAYER_SCHEMAS in a chosen UTM zone.

North-star: we do not ship binary shapefiles. QGIS already knows how to write
them, so we define the schema in Python and generate empty, correctly-projected
templates on demand — one set per zone, encoded UTF-8.
"""

import os

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsField,
    QgsFields,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsProject,
)

from . import config
from . import crs as crs_mod

_TYPE_MAP = {
    "int": (QVariant.Int, "integer", 0),
    "long": (QVariant.LongLong, "integer64", 0),
    "double": (QVariant.Double, "double", 0),
    "date": (QVariant.Date, "date", 0),
}

_WKB = {
    "Point": QgsWkbTypes.Point,
    "LineString": QgsWkbTypes.LineString,
    "Polygon": QgsWkbTypes.Polygon,
}


def _fields_for(schema):
    fields = QgsFields()
    for name, spec in schema["fields"]:
        if spec.startswith("string"):
            width = int(spec.split(":")[1]) if ":" in spec else 254
            fields.append(QgsField(name, QVariant.String, "string", width))
        else:
            qvar, typename, _ = _TYPE_MAP[spec]
            fields.append(QgsField(name, qvar, typename))
    return fields


def create_template(name, out_dir, zone, overwrite=False):
    """Write one empty shapefile <name>.shp and return its path."""
    schema = config.LAYER_SCHEMAS[name]
    path = os.path.join(out_dir, f"{name}.shp")
    if os.path.exists(path) and not overwrite:
        return path

    fields = _fields_for(schema)
    wkb = _WKB[schema["geometry"]]
    crs = crs_mod.zone_crs(zone)

    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "ESRI Shapefile"
    opts.fileEncoding = "UTF-8"

    ctx = QgsProject.instance().transformContext()
    writer = QgsVectorFileWriter.create(path, fields, wkb, crs, ctx, opts)
    try:
        if writer.hasError() != QgsVectorFileWriter.NoError:
            raise RuntimeError(writer.errorMessage())
    finally:
        del writer  # flush + close so the .shp/.dbf/.prj are written to disk
    return path


def create_all(out_dir, zone, overwrite=False):
    """Create every template layer; return {name: path}."""
    os.makedirs(out_dir, exist_ok=True)
    return {n: create_template(n, out_dir, zone, overwrite)
            for n in config.LAYER_SCHEMAS}


def add_to_project(paths, group_name=None):
    """Load template shapefiles into the current project (bottom→top order).

    Returns the list of QgsVectorLayer added.
    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    parent = root.insertGroup(0, group_name) if group_name else root

    added = []
    for name in config.TEMPLATE_ORDER:
        path = paths.get(name)
        if not path or not os.path.exists(path):
            continue
        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            continue
        project.addMapLayer(layer, addToLegend=False)
        parent.insertLayer(0, layer)
        added.append(layer)
    return added
