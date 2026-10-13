# -*- coding: utf-8 -*-
"""Processing provider for Calculate Geometry (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import CalculateGeometryAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class CalculateGeometryProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(CalculateGeometryAlgorithm())

    def id(self):
        return 'calculate_geometry'

    def name(self):
        return 'Calculate Geometry'

    def longName(self):
        return 'Calculate Geometry (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.svg'))
