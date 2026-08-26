# -*- coding: utf-8 -*-
"""Transliterate Data — QGIS plugin entry point."""


def classFactory(iface):
    from .plugin_main import TransliterateDataPlugin
    return TransliterateDataPlugin(iface)
