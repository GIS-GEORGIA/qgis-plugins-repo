# -*- coding: utf-8 -*-
"""Processing provider for Owners Analyzer (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import (
    CountUniqueValuesAlgorithm,
    ExtractByKeywordsAlgorithm,
    SelectByKeywordsAlgorithm,
)

_DIR = os.path.dirname(os.path.abspath(__file__))


class OwnersAnalyzerProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(CountUniqueValuesAlgorithm())
        self.addAlgorithm(ExtractByKeywordsAlgorithm())
        self.addAlgorithm(SelectByKeywordsAlgorithm())

    def id(self):
        return 'owners_analyzer'

    def name(self):
        return 'Owners Analyzer'

    def longName(self):
        return 'Owners Analyzer (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.png'))
