# -*- coding: utf-8 -*-
"""Name-based symbology + labelling.

`apply_style(layer)` normalises the layer name (strips digits/suffixes) and
applies a renderer *and* a label configuration that matches the official
cadastral drawing look. This is the "styles recognise layers by name and set
both symbol and label" requirement, done programmatically so there are no
fragile .qml files to keep in sync with the schema.
"""

import re

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsUnitTypes,
)

RED = "#e60000"
YELLOW = "#ffcc00"
GRAY = "#7f7f7f"
BLACK = "#000000"


def normalise(name):
    """'topo_point1' -> 'topo_point', 'Nakveti 2' -> 'nakveti'."""
    n = name.strip().lower()
    n = re.sub(r"[\s\-]+", "_", n)
    n = re.sub(r"\d+$", "", n)          # trailing digits
    n = re.sub(r"_+$", "", n)
    return n


# --------------------------------------------------------------------------- #
# Text format + labelling helpers
# --------------------------------------------------------------------------- #
def _text_format(color=BLACK, size=8.0, bold=False, buffer=True):
    fmt = QgsTextFormat()
    font = fmt.font()
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSize(size)
    fmt.setSizeUnit(QgsUnitTypes.RenderPoints)
    fmt.setColor(QColor(color))
    if buffer:
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.8)
        buf.setColor(QColor("white"))
        fmt.setBuffer(buf)
    return fmt


def _labeling(expression, text_format, placement=None):
    s = QgsPalLayerSettings()
    s.fieldName = expression
    s.isExpression = True
    s.setFormat(text_format)
    s.placement = placement if placement is not None else Qgis.LabelPlacement.OverPoint
    return QgsVectorLayerSimpleLabeling(s)


# --------------------------------------------------------------------------- #
# Per-layer builders
# --------------------------------------------------------------------------- #
def _style_nakveti(layer):
    sym = QgsFillSymbol.createSimple({
        "color": "0,0,0,0",            # transparent fill
        "outline_color": RED,
        "outline_width": "0.6",
        "outline_width_unit": "MM",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    # Area label at centroid, e.g. "2078 კვ.მ."
    expr = ("round(coalesce(\"Shape_Area\", $area)) || ' კვ.მ.'")
    lab = _labeling(expr, _text_format(RED, 10, bold=True),
                    Qgis.LabelPlacement.AroundPoint)
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_servituti(layer):
    sym = QgsFillSymbol.createSimple({
        "style": "b_diagonal",          # hatched — "ვალდებულება"
        "color": GRAY,
        "outline_color": BLACK,
        "outline_width": "0.3",
        "outline_style": "dash",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    lab = _labeling("\"OBL_TYPE\"", _text_format(BLACK, 7))
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_shenoba(layer):
    sym = QgsFillSymbol.createSimple({
        "color": "200,200,200,120",
        "outline_color": BLACK,
        "outline_width": "0.3",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    # "01 / 2"  ->  building number / floors
    expr = "coalesce(\"BLD_NUM\",'') || ' / ' || coalesce(\"FLOORS\",'')"
    lab = _labeling(expr, _text_format(BLACK, 8, bold=True))
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_topo_line(layer):
    sym = QgsLineSymbol.createSimple({
        "line_color": BLACK,
        "line_width": "0.4",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    lab = _labeling("\"type\"", _text_format(BLACK, 7),
                    Qgis.LabelPlacement.Line)
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_topo_point(layer):
    sym = QgsMarkerSymbol.createSimple({
        "name": "cross2",               # "A!" boundary vertex marker
        "color": BLACK,
        "size": "2.0",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    lab = _labeling("\"POINT_ID\"", _text_format(BLACK, 8, bold=True))
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_topo_polygon(layer):
    sym = QgsFillSymbol.createSimple({
        "color": "255,255,190,80",
        "outline_color": GRAY,
        "outline_width": "0.2",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))


def _style_lease_polygon(layer):
    """Floor-plan lease/servitude area — hatched, labelled with the comment."""
    sym = QgsFillSymbol.createSimple({
        "style": "b_diagonal",
        "color": YELLOW,
        "outline_color": BLACK,
        "outline_width": "0.3",
        "outline_style": "dash",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    lab = _labeling("\"Coment\"", _text_format(BLACK, 7))
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


def _style_unit_polygon(layer):
    """Floor-plan unit (flat) — grey fill, label 'flat / floor'."""
    sym = QgsFillSymbol.createSimple({
        "color": "200,200,200,110",
        "outline_color": BLACK,
        "outline_width": "0.25",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(sym))
    expr = ("coalesce(\"FLAT\",'') || "
            "if(coalesce(\"FLOOR\",\"flooo\") is null,'',' / ' || "
            "coalesce(\"FLOOR\",\"flooo\"))")
    lab = _labeling(expr, _text_format(BLACK, 7, bold=True))
    layer.setLabeling(lab)
    layer.setLabelsEnabled(True)


_BUILDERS = {
    "nakveti": _style_nakveti,          # nakveti / nakveTi
    "cadastre_parcels": _style_nakveti,  # bulk fetch results (same red look)
    "servituti": _style_servituti,
    "shenoba": _style_shenoba,
    "topo_line": _style_topo_line,
    "topo_point": _style_topo_point,
    "topo_polygon": _style_topo_polygon,
    "topo_poligon": _style_topo_polygon,   # real template spelling
    "xazobrivi": _style_topo_line,      # linear structure alias
    # floor-plan (შიდა აზომვითი ნახაზი)
    "lease_polygon": _style_lease_polygon,
    "unit_line": _style_topo_line,
    "unit_polygon": _style_unit_polygon,
}


def apply_style(layer):
    """Apply symbology + labels to a layer based on its (normalised) name.

    Returns True if a matching style was applied.
    """
    key = normalise(layer.name())
    builder = _BUILDERS.get(key)
    if builder is None:
        return False
    builder(layer)
    layer.triggerRepaint()
    if hasattr(layer, "emitStyleChanged"):
        layer.emitStyleChanged()
    return True


def apply_to_project(project):
    """Apply name-based styles to every vector layer in the project."""
    applied = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        try:
            if apply_style(layer):
                applied.append(layer.name())
        except Exception:
            continue
    return applied
