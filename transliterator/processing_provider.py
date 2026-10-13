# -*- coding: utf-8 -*-
"""Processing provider for Transliterator (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import TransliterateFieldAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class TransliteratorProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(TransliterateFieldAlgorithm())

    def id(self):
        return 'transliterator'

    def name(self):
        return 'Transliterator'

    def longName(self):
        return 'Transliterator (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.png'))
