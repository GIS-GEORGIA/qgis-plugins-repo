# -*- coding: utf-8 -*-
"""Build the A4 cadastral print layout programmatically.

Reproduces the reference sheet: titled map frame with a coordinate grid and
tick labels, a north arrow, a scale bar, a legend and a lower title block whose
fields are *dynamic expressions* — the date, the plot area (pulled from the
nakveti layer), the cadastral code and the CRS name all update themselves.
"""

import glob
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.core import (
    QgsProject,
    QgsPrintLayout,
    QgsLayoutItemPage,
    QgsLayoutItemMap,
    QgsLayoutItemLabel,
    QgsLayoutItemScaleBar,
    QgsLayoutItemLegend,
    QgsLayoutItemPicture,
    QgsLayoutItemMapGrid,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsUnitTypes,
    QgsApplication,
    QgsRectangle,
)

LAYOUT_NAME = "საკადასტრო ნახაზი / Cadastral drawing"

# A4 portrait, millimetres.
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 8.0


def _find_north_svg():
    """Locate a proper north-arrow SVG shipped with QGIS, or return ''."""
    candidates = []
    for base in QgsApplication.svgPaths():
        candidates += glob.glob(os.path.join(base, "**", "*.svg"), recursive=True)
    # Prefer an explicit "NorthArrow" file, then anything with "north".
    for want in ("northarrow", "north"):
        for path in candidates:
            if want in os.path.basename(path).lower():
                return path
    return ""


def _label(layout, text, x, y, w, h, size=8.0, bold=False, html=False,
           align=Qt.AlignLeft):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    if html:
        item.setMode(QgsLayoutItemLabel.ModeHtml)
    font = QFont()
    font.setPointSizeF(size)
    font.setBold(bold)
    item.setFont(font)
    item.setHAlign(align)
    item.setVAlign(Qt.AlignVCenter)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    return item


def _find_layer(name_stem):
    from .styles import normalise
    for layer in QgsProject.instance().mapLayers().values():
        if normalise(layer.name()) == name_stem:
            return layer
    return None


def build_layout(scale=1000, replace=True):
    """Create (or replace) the layout and return it."""
    project = QgsProject.instance()
    manager = project.layoutManager()

    existing = manager.layoutByName(LAYOUT_NAME)
    if existing:
        if not replace:
            return existing
        manager.removeLayout(existing)

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(LAYOUT_NAME)
    # Force A4 *portrait* (initializeDefaults may hand back landscape).
    page = layout.pageCollection().pages()[0]
    page.setPageSize("A4", QgsLayoutItemPage.Portrait)

    # --- Title -------------------------------------------------------------
    _label(layout, "საკადასტრო აგეგმვითი/აზომვითი ნახაზი",
           MARGIN, MARGIN, PAGE_W - 2 * MARGIN, 8,
           size=13, bold=True, align=Qt.AlignHCenter)

    # --- Map ---------------------------------------------------------------
    map_top = MARGIN + 10
    map_h = 185
    map_w = PAGE_W - 2 * MARGIN
    map_item = QgsLayoutItemMap(layout)
    map_item.setRect(0, 0, map_w, map_h)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(QgsLayoutPoint(MARGIN, map_top, QgsUnitTypes.LayoutMillimeters))
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, QgsUnitTypes.LayoutMillimeters))
    map_item.setFrameEnabled(True)

    nakveti = _find_layer("nakveti")
    if nakveti and nakveti.extent() and not nakveti.extent().isEmpty():
        ext = QgsRectangle(nakveti.extent())
        ext.scale(1.4)  # padding around the plot
        map_item.zoomToExtent(ext)
    map_item.setScale(float(scale))

    _configure_grid(map_item)

    # --- North arrow -------------------------------------------------------
    svg = _find_north_svg()
    if svg:
        pic = QgsLayoutItemPicture(layout)
        pic.setPicturePath(svg)
        layout.addLayoutItem(pic)
        pic.attemptMove(QgsLayoutPoint(PAGE_W - MARGIN - 16, map_top + 3,
                                       QgsUnitTypes.LayoutMillimeters))
        pic.attemptResize(QgsLayoutSize(12, 12, QgsUnitTypes.LayoutMillimeters))
    else:
        _label(layout, "N ↑", PAGE_W - MARGIN - 16, map_top + 3, 12, 8,
               size=11, bold=True, align=Qt.AlignHCenter)

    # --- Scale bar ---------------------------------------------------------
    bar = QgsLayoutItemScaleBar(layout)
    bar.setStyle("Single Box")
    bar.setLinkedMap(map_item)
    bar.setUnits(QgsUnitTypes.DistanceMeters)
    bar.setUnitLabel("m / მ")
    bar.applyDefaultSize()
    layout.addLayoutItem(bar)
    bar.attemptMove(QgsLayoutPoint(MARGIN + 2, map_top + map_h + 2,
                                   QgsUnitTypes.LayoutMillimeters))

    # --- Legend ------------------------------------------------------------
    legend = QgsLayoutItemLegend(layout)
    legend.setTitle("პირობითი აღნიშვნები / Legend")
    legend.setLinkedMap(map_item)
    legend.setAutoUpdateModel(True)
    _shrink_legend_fonts(legend)
    layout.addLayoutItem(legend)
    legend.attemptMove(QgsLayoutPoint(MARGIN, map_top + map_h + 12,
                                      QgsUnitTypes.LayoutMillimeters))
    legend.attemptResize(QgsLayoutSize(66, 55, QgsUnitTypes.LayoutMillimeters))

    _build_title_block(layout, map_top + map_h + 12)
    return layout


def _shrink_legend_fonts(legend):
    """Smaller legend fonts so the title doesn't run into the info block."""
    try:
        from qgis.core import QgsLegendStyle
        title_f = QFont(); title_f.setPointSizeF(8.0); title_f.setBold(True)
        item_f = QFont(); item_f.setPointSizeF(7.0)
        legend.setStyleFont(QgsLegendStyle.Title, title_f)
        legend.setStyleFont(QgsLegendStyle.SymbolLabel, item_f)
    except Exception:
        pass


def _configure_grid(map_item):
    grid = map_item.grid()
    grid.setEnabled(True)
    grid.setStyle(QgsLayoutItemMapGrid.Cross)
    grid.setCrossLength(2.0)
    grid.setIntervalX(50.0)
    grid.setIntervalY(50.0)
    grid.setAnnotationEnabled(True)
    grid.setAnnotationPrecision(0)
    grid.setAnnotationFrameDistance(1.0)
    try:
        # Coordinates only on the left + bottom (avoids clipping the right edge
        # and overlapping the title on top).
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll,
                                  QgsLayoutItemMapGrid.Top)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll,
                                  QgsLayoutItemMapGrid.Right)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.ShowAll,
                                  QgsLayoutItemMapGrid.Left)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.ShowAll,
                                  QgsLayoutItemMapGrid.Bottom)
        grid.setAnnotationPosition(QgsLayoutItemMapGrid.OutsideMapFrame,
                                   QgsLayoutItemMapGrid.Left)
        grid.setAnnotationPosition(QgsLayoutItemMapGrid.OutsideMapFrame,
                                   QgsLayoutItemMapGrid.Bottom)
        grid.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical,
                                    QgsLayoutItemMapGrid.Left)
    except Exception:
        pass


def _build_title_block(layout, top):
    """Right-hand info block with dynamic expression labels."""
    x = MARGIN + 74
    w = PAGE_W - MARGIN - x
    row = 7
    y = top

    fields = [
        ("მისამართი / Address:",
         "[% aggregate('nakveti','concatenate',\"ADDRESS\",concatenator:='') %]"),
        ("საკადასტრო კოდი / Code:",
         "[% aggregate('nakveti','concatenate',\"LEGAL_DOC\",concatenator:=', ') %]"),
        ("ფართობი / Area (კვ.მ):",
         "[% round(aggregate('nakveti','sum', coalesce(\"Shape_Area\", $area))) %]"),
        ("დანიშნულება / Designation:",
         "[% aggregate('nakveti','concatenate',\"FUNCTION\",concatenator:='') %]"),
        ("სისტემა / CRS:",
         "[% @project_crs %]  ( [% @project_crs_description %] )"),
        ("თარიღი / Date:",
         "[% format_date(now(),'dd.MM.yyyy') %]"),
    ]
    for caption, expr in fields:
        _label(layout, caption, x, y, w * 0.42, row, size=7, bold=True)
        lab = _label(layout, expr, x + w * 0.42, y, w * 0.58, row, size=7)
        y += row
    return y
