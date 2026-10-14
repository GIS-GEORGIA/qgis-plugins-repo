# -*- coding: utf-8 -*-
"""QGIS Environment Manager - what this QGIS is, which plugins fit QGIS 4, what the plugins need from the system."""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    from .plugin import EnvManagerPlugin
    return EnvManagerPlugin(iface)
