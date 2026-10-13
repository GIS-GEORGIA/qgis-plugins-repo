# -*- coding: utf-8 -*-
"""Transliterate field — Georgian <-> Latin text fields as a Processing algorithm."""
from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
)

from .translit_core import georgian_to_latin, latin_to_georgian

_DIRECTIONS = ['Georgian → Latin', 'Latin → Georgian']
_SUFFIX = ['_lat', '_geo']
_CONVERT = [georgian_to_latin, latin_to_georgian]


class TransliterateFieldAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELDS = 'FIELDS'
    DIRECTION = 'DIRECTION'
    REPLACE = 'REPLACE'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'transliterate_field'

    def displayName(self):
        return 'Transliterate field'

    def group(self):
        return 'Attribute tools'

    def groupId(self):
        return 'attribute_tools'

    def tags(self):
        return ['transliterate', 'georgian', 'latin', 'ქართული', 'ტრანსლიტერაცია']

    def shortHelpString(self):
        return (
            'Converts text fields between Georgian script and Latin '
            '(one-to-one letter map: თ→T, ჟ→J, ღ→R, შ→S, ჩ→C, ძ→Z, წ→w, ჭ→W …).\n\n'
            'By default the result is written to a new field named '
            '"<first 8 chars of field>_lat" (or "_geo"); an existing field with that '
            'name is overwritten. Tick "Replace" to overwrite the source fields instead.'
        )

    def createInstance(self):
        return TransliterateFieldAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input layer', [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELDS, 'Fields to transliterate', parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.String, allowMultiple=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.DIRECTION, 'Direction', options=_DIRECTIONS, defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.REPLACE, 'Replace the source fields (instead of adding new fields)',
            defaultValue=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Transliterated'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        names = self.parameterAsStrings(parameters, self.FIELDS, context)
        if not names:
            raise QgsProcessingException('Select at least one field.')
        direction = self.parameterAsEnum(parameters, self.DIRECTION, context)
        replace = self.parameterAsBoolean(parameters, self.REPLACE, context)
        convert = _CONVERT[direction]

        fields = source.fields()
        out_fields = fields
        # (source index, destination index)
        pairs = []
        for name in names:
            src_idx = fields.lookupField(name)
            if src_idx < 0:
                raise QgsProcessingException('Field not found: {}'.format(name))
            if replace:
                pairs.append((src_idx, src_idx))
                continue
            new_name = name[:8] + _SUFFIX[direction]
            dst_idx = out_fields.lookupField(new_name)
            if dst_idx < 0:
                out_fields.append(QgsField(new_name, QMetaType.Type.QString))
                dst_idx = out_fields.count() - 1
            pairs.append((src_idx, dst_idx))

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            source.wkbType(), source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = source.featureCount()
        step = 100.0 / total if total else 0
        n_fields = out_fields.count()
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            attrs = list(feat.attributes())
            attrs.extend([None] * (n_fields - len(attrs)))
            for src_idx, dst_idx in pairs:
                val = feat.attribute(src_idx)
                if val is not None and not (hasattr(val, 'isNull') and val.isNull()):
                    attrs[dst_idx] = convert(str(val))
                elif dst_idx != src_idx:
                    attrs[dst_idx] = None
            out = QgsFeature(out_fields)
            out.setGeometry(feat.geometry())
            out.setAttributes(attrs)
            sink.addFeature(out)
            feedback.setProgress(int(i * step))
        return {self.OUTPUT: dest_id}
