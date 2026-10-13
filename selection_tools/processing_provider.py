# -*- coding: utf-8 -*-
"""Processing provider for Selection Tools (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .processing_algorithms import (
    AddAutoincrementKeyAlgorithm,
    DefinitionQueryFromSelectionAlgorithm,
    LayerFromSelectionAlgorithm,
)

_DIR = os.path.dirname(os.path.abspath(__file__))


class SelectionToolsProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        self.addAlgorithm(LayerFromSelectionAlgorithm())
        self.addAlgorithm(DefinitionQueryFromSelectionAlgorithm())
        self.addAlgorithm(AddAutoincrementKeyAlgorithm())

    def id(self):
        return 'selection_tools'

    def name(self):
        return 'Selection Tools'

    def longName(self):
        return 'Selection Tools (GIS Georgia)'

    def icon(self):
        return QIcon(os.path.join(_DIR, 'icon.svg'))
