# -*- coding: utf-8 -*-
"""Processing provider for Transliterate Data (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import TransliterateFolderAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class TransliterateDataProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(TransliterateFolderAlgorithm())

    def id(self):
        return 'transliterate_data'

    def name(self):
        return 'Transliterate Data'

    def longName(self):
        return 'Transliterate Data (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.svg'))
