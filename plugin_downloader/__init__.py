# -*- coding: utf-8 -*-
"""
QGIS ფლაგინის შესვლის წერტილი. QGIS ამ ფუნქციას იძახებს ფლაგინის ჩატვირთვისას.
"""


def classFactory(iface):
    try:
        from .plugin import PluginDownloader
    except ImportError:
        from plugin import PluginDownloader
    return PluginDownloader(iface)
