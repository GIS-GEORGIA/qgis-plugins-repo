# -*- coding: utf-8 -*-
"""Processing provider for Basemap Loader (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import AddBasemapAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class BasemapLoaderProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(AddBasemapAlgorithm())

    def id(self):
        return 'basemap_loader'

    def name(self):
        return 'Basemap Loader'

    def longName(self):
        return 'Basemap Loader (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'logo.png'))
