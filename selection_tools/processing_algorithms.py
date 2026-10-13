# -*- coding: utf-8 -*-
"""Selection Tools as Processing algorithms (layer from selection, definition query).

Both work on the *selection of the layer object they receive*: in the QGIS GUI that is
the project layer's current selection; in a model, chain them after a "Select by
expression" / "Select by location" step. They touch the project / the layer itself, so
they run on the main thread.
"""
from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputMapLayer,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterVectorLayer,
)

from .selection_ops import (
    add_autoincrement_key,
    apply_definition_query_from_selection,
    make_layer_from_selection,
)


class _SelectionBase(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    ADD_KEY = 'ADD_KEY'
    OUT_LAYER = 'OUTPUT'
    OUT_COUNT = 'COUNT'
    OUT_SUBSET = 'SUBSET'

    def group(self):
        return 'Selection'

    def groupId(self):
        return 'selection'

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def _add_common_parameters(self):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, 'Layer with a selection'))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ADD_KEY,
            'If no stable key is found, add an auto-increment field to the source '
            '(modifies the data source!)', defaultValue=False))

    def _status_error(self, status, subset):
        if status == 'no_selection':
            return 'The layer has no selected features.'
        if status == 'empty':
            return ('No subset query reproduces the selection (tried: {}). Tick the '
                    'auto-increment option to add a stable key.'.format(subset or '-'))
        return 'Failed: {}'.format(status)


class LayerFromSelectionAlgorithm(_SelectionBase):

    def name(self):
        return 'layer_from_selection'

    def displayName(self):
        return 'Make layer from selected features'

    def shortHelpString(self):
        return (
            'ArcGIS "Make Layer From Selected Features": adds a new layer on the same '
            'data source, filtered by a subset query to the selected features. No file '
            'is written; the new layer is added to the project.\n\n'
            'Requires a selection on the input layer (use "Select by expression" or '
            '"Select by location" before it in a model).'
        )

    def createInstance(self):
        return LayerFromSelectionAlgorithm()

    def initAlgorithm(self, config=None):
        self._add_common_parameters()
        self.addOutput(QgsProcessingOutputMapLayer(self.OUT_LAYER, 'New layer'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_COUNT, 'Feature count'))
        self.addOutput(QgsProcessingOutputString(self.OUT_SUBSET, 'Subset query'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        add_key = self.parameterAsBoolean(parameters, self.ADD_KEY, context)

        new, status, count, subset = make_layer_from_selection(layer)
        if status == 'empty' and add_key:
            field, key_status = add_autoincrement_key(layer)
            if field is None:
                raise QgsProcessingException(
                    'Could not add an auto-increment key: {}'.format(key_status))
            feedback.pushInfo('Added key field "{}" to the source.'.format(field))
            new, status, count, subset = make_layer_from_selection(layer)
        if status != 'ok':
            raise QgsProcessingException(self._status_error(status, subset))

        feedback.pushInfo('{}: {} feature(s), subset: {}'.format(new.name(), count, subset))
        return {self.OUT_LAYER: new.id(), self.OUT_COUNT: count, self.OUT_SUBSET: subset}


class DefinitionQueryFromSelectionAlgorithm(_SelectionBase):

    def name(self):
        return 'definition_query_from_selection'

    def displayName(self):
        return 'Definition query from selection'

    def shortHelpString(self):
        return (
            'ArcGIS "Generate Definition Query from Selection": sets the layer\'s own '
            'subset query so it shows only the selected features (combined with any '
            'existing filter by AND).\n\n'
            'Requires a selection on the input layer.'
        )

    def createInstance(self):
        return DefinitionQueryFromSelectionAlgorithm()

    def initAlgorithm(self, config=None):
        self._add_common_parameters()
        self.addOutput(QgsProcessingOutputMapLayer(self.OUT_LAYER, 'Filtered layer'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_COUNT, 'Feature count'))
        self.addOutput(QgsProcessingOutputString(self.OUT_SUBSET, 'Subset query'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        add_key = self.parameterAsBoolean(parameters, self.ADD_KEY, context)

        status, count, subset = apply_definition_query_from_selection(layer)
        if status == 'empty' and add_key:
            field, key_status = add_autoincrement_key(layer)
            if field is None:
                raise QgsProcessingException(
                    'Could not add an auto-increment key: {}'.format(key_status))
            feedback.pushInfo('Added key field "{}" to the source.'.format(field))
            status, count, subset = apply_definition_query_from_selection(layer)
        if status != 'ok':
            raise QgsProcessingException(self._status_error(status, subset))

        feedback.pushInfo('{}: {} feature(s), subset: {}'.format(layer.name(), count, subset))
        return {self.OUT_LAYER: layer.id(), self.OUT_COUNT: count, self.OUT_SUBSET: subset}


class AddAutoincrementKeyAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    OUT_FIELD = 'FIELD'
    OUT_LAYER = 'OUTPUT'

    def name(self):
        return 'add_autoincrement_key'

    def displayName(self):
        return 'Add auto-increment key to source'

    def group(self):
        return 'Selection'

    def groupId(self):
        return 'selection'

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def shortHelpString(self):
        return (
            'Adds a unique integer field (1..N) to the layer\'s own data source, e.g. '
            'a shapefile without a primary key, so subset queries built from a '
            'selection keep working after the project is saved.\n\n'
            'WARNING: this modifies the data source (a new column). The layer must not '
            'be in edit mode.'
        )

    def createInstance(self):
        return AddAutoincrementKeyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT, 'Layer'))
        self.addOutput(QgsProcessingOutputString(self.OUT_FIELD, 'Key field'))
        self.addOutput(QgsProcessingOutputMapLayer(self.OUT_LAYER, 'Layer'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field, status = add_autoincrement_key(layer)
        if field is None:
            raise QgsProcessingException('Could not add the key field: {}'.format(status))
        feedback.pushInfo('Added key field "{}".'.format(field))
        return {self.OUT_FIELD: field, self.OUT_LAYER: layer.id()}
