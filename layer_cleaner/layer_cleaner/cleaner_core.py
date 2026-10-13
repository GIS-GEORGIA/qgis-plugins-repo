# -*- coding: utf-8 -*-
"""Project-level helpers shared by the Layer Cleaner dialog and its Processing algorithms."""
from qgis.core import QgsProject, QgsRasterLayer

BASE_LAYERS = [
    ("Google Satellite Hybrid",
     "type=xyz&url=https://mt1.google.com/vt/lyrs=y%26x={x}%26y={y}%26z={z}"),
    ("OpenStreetMap",
     "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
]
KEEP_NAMES = [name for name, _url in BASE_LAYERS]


def layers_to_remove(project=None, keep_names=None, keep_ids=None):
    """Ids of project layers whose name is not in keep_names and id not in keep_ids."""
    project = project or QgsProject.instance()
    keep_names = set(KEEP_NAMES if keep_names is None else keep_names)
    keep_ids = set(keep_ids or ())
    return [lyr.id() for lyr in project.mapLayers().values()
            if lyr.name() not in keep_names and lyr.id() not in keep_ids]


def remove_layers(layer_ids, project=None):
    project = project or QgsProject.instance()
    project.removeMapLayers(list(layer_ids))
    return len(layer_ids)


def add_base_layers(project=None):
    """Add the base layers that are missing. Returns the list of added names."""
    project = project or QgsProject.instance()
    existing = {lyr.name() for lyr in project.mapLayers().values()}
    added = []
    for name, uri in BASE_LAYERS:
        if name in existing:
            continue
        layer = QgsRasterLayer(uri, name, "wms")
        if layer.isValid():
            project.addMapLayer(layer)
            added.append(name)
    return added
