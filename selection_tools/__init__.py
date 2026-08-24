# -*- coding: utf-8 -*-
"""Selection Tools — QGIS plugin entry point."""


def classFactory(iface):
    from .plugin_main import SelectionToolsPlugin
    return SelectionToolsPlugin(iface)
