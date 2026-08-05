# -*- coding: utf-8 -*-
"""Georgian Cadastre — fetch NAPR parcels by cadastral code into QGIS.

Data source: maps.gov.ge (public search + geometry API).
"""


def classFactory(iface):  # noqa: N802 (QGIS-required name)
    """Entry point QGIS calls to load the plugin."""
    from .plugin import GeorgianCadastrePlugin

    return GeorgianCadastrePlugin(iface)
