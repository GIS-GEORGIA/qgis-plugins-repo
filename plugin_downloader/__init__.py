# -*- coding: utf-8 -*-
"""
QGIS დანამატის შესვლის წერტილი. QGIS ამ ფუნქციას იძახებს დანამატის ჩატვირთვისას.
"""


def classFactory(iface):
    try:
        from .plugin import PluginDownloader
    except ImportError:
        from plugin import PluginDownloader
    return PluginDownloader(iface)
