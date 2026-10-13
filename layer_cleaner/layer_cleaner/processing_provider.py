# -*- coding: utf-8 -*-
"""Processing provider for Layer Cleaner (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import AddBaseLayersAlgorithm, RemoveLayersAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class LayerCleanerProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(RemoveLayersAlgorithm())
        self.addAlgorithm(AddBaseLayersAlgorithm())

    def id(self):
        return 'layer_cleaner'

    def name(self):
        return 'Layer Cleaner'

    def longName(self):
        return 'Layer Cleaner (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icons', 'icon.png'))
