# -*- coding: utf-8 -*-
"""GIS Georgia Hub - one place in QGIS to browse, install and update the GIS GEORGIA plugins."""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    from .plugin import GisGeorgiaHubPlugin
    return GisGeorgiaHubPlugin(iface)
