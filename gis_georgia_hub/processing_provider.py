# -*- coding: utf-8 -*-
"""Processing provider of GIS Georgia Hub (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .processing_algorithms import InstallPluginAlgorithm, ListCatalogAlgorithm, UpdatePluginsAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class HubProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(InstallPluginAlgorithm())
        self.addAlgorithm(UpdatePluginsAlgorithm())
        self.addAlgorithm(ListCatalogAlgorithm())

    def id(self):
        return "gis_georgia_hub"

    def name(self):
        return "GIS Georgia Hub"

    def longName(self):
        return "GIS Georgia Hub (GIS Georgia)"

    def icon(self):
        return QIcon(os.path.join(_DIR, "icon.svg"))
