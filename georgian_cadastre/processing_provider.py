# -*- coding: utf-8 -*-
"""Processing provider for Georgian Cadastre (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import FetchParcelsAlgorithm, ParcelsNearPointAlgorithm

_DIR = os.path.dirname(os.path.abspath(__file__))


class GeorgianCadastreProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(FetchParcelsAlgorithm())
        self.addAlgorithm(ParcelsNearPointAlgorithm())

    def id(self):
        return 'georgian_cadastre'

    def name(self):
        return 'Georgian Cadastre'

    def longName(self):
        return 'Georgian Cadastre (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.svg'))
