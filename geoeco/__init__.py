"""GeoEco QGIS plugin entry point."""


def classFactory(iface):
    from .plugin_main import GeoEcoPlugin
    return GeoEcoPlugin(iface)
