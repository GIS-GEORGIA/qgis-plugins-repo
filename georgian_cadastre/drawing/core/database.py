# -*- coding: utf-8 -*-
"""Import a registered-plots dataset (File GDB / MDB / SHP / GPKG) and arrange
the plots grouped by region in the layer tree.

Efficient by design: instead of copying features into per-region layers, we add
one lightweight layer per region that shares the same data source but carries a
subset filter. Works on datasets of any size.
"""

import os
import re

from qgis.core import QgsVectorLayer, QgsProject

from . import config
from . import i18n

# Field-name hints for the cadastral-code column (case-insensitive contains).
_CODE_HINTS = ("cad", "code", "kod", "lbl", "legal_doc", "parcel")


def list_sublayers(path):
    """Return [(layer_name, uri)] of vector sublayers in the source."""
    base = QgsVectorLayer(path, "probe", "ogr")
    subs = base.dataProvider().subLayers() if base.isValid() else []
    result = []
    if subs:
        for s in subs:
            # format: index:name:featureCount:geomType  (':' separated)
            parts = s.split(base.dataProvider().sublayerSeparator())
            name = parts[1] if len(parts) > 1 else parts[0]
            result.append((name, f"{path}|layername={name}"))
    elif base.isValid():
        result.append((os.path.splitext(os.path.basename(path))[0], path))
    return result


def detect_code_field(layer):
    names = [f.name() for f in layer.fields()]
    for n in names:
        low = n.lower()
        if any(h in low for h in _CODE_HINTS):
            return n
    return None


def region_of(code_value):
    """Map a cadastral code / value to (prefix, region_label)."""
    if code_value is None:
        return "??", i18n.tr("error")
    m = re.match(r"\s*(\d{2})", str(code_value))
    prefix = m.group(1) if m else "??"
    region = config.REGION_BY_PREFIX.get(prefix)
    lang = i18n.current_language()
    label = region[lang] if region else prefix
    return prefix, label


def _distinct_prefixes(layer, field):
    idx = layer.fields().indexOf(field)
    prefixes = {}
    for val in layer.uniqueValues(idx):
        prefix, label = region_of(val)
        prefixes.setdefault(prefix, label)
    return prefixes


def import_grouped(path, group_field=None, project=None):
    """Import every sublayer, splitting plot layers into per-region subgroups.

    Returns a summary dict {sublayer_name: [region_labels...]}.
    """
    project = project or QgsProject.instance()
    root = project.layerTreeRoot()
    top = root.insertGroup(0, os.path.basename(path.rstrip("/\\")) or "import")

    summary = {}
    for name, uri in list_sublayers(path):
        probe = QgsVectorLayer(uri, name, "ogr")
        if not probe.isValid():
            continue
        field = group_field if (group_field and probe.fields().indexOf(group_field) >= 0) \
            else detect_code_field(probe)

        if not field:
            project.addMapLayer(probe, addToLegend=False)
            top.insertLayer(0, probe)
            summary[name] = ["(ungrouped)"]
            continue

        prefixes = _distinct_prefixes(probe, field)
        if len(prefixes) <= 1:
            project.addMapLayer(probe, addToLegend=False)
            top.insertLayer(0, probe)
            summary[name] = list(prefixes.values()) or ["(all)"]
            continue

        group = top.insertGroup(0, name)
        labels = []
        for prefix, label in sorted(prefixes.items()):
            sub = QgsVectorLayer(uri, f"{name} — {label}", "ogr")
            sub.setSubsetString(f"\"{field}\" LIKE '{prefix}%'")
            project.addMapLayer(sub, addToLegend=False)
            group.insertLayer(0, sub)
            labels.append(label)
        summary[name] = labels
    return summary
