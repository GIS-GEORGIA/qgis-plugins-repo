# -*- coding: utf-8 -*-
"""Calculate Geometry — QGIS plugin POC.

Tracking issue: https://github.com/qgis/QGIS/issues/66902
"""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Entry point QGIS calls to load the plugin."""
    from .plugin import CalculateGeometryPlugin

    return CalculateGeometryPlugin(iface)
