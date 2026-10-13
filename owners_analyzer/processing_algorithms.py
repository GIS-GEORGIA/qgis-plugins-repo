# -*- coding: utf-8 -*-
"""Owners Analyzer as Processing algorithms."""
from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputMapLayer,
    QgsProcessingOutputNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorLayer,
    QgsWkbTypes,
)

from . import analysis_core as core

_SORT = ['Georgian alphabet (ა-ჰ)', 'Count, descending']


class CountUniqueValuesAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    FIELD = 'FIELD'
    SORT = 'SORT'
    OUTPUT = 'OUTPUT'
    OUTPUT_TXT = 'OUTPUT_TXT'
    OUT_UNIQUE = 'UNIQUE'

    def name(self):
        return 'count_unique_values'

    def displayName(self):
        return 'Count unique values (owners)'

    def group(self):
        return 'Owners analysis'

    def groupId(self):
        return 'owners_analysis'

    def tags(self):
        return ['owners', 'unique', 'count', 'statistics', 'მფლობელები']

    def shortHelpString(self):
        return (
            'Counts how many times each distinct value of a field occurs (values are '
            'trimmed; empty values are skipped) and writes them to a table sorted in '
            'Georgian alphabetical order or by count. Optionally also writes the '
            '"value | count" text report of the Owners Analyzer dialog.'
        )

    def createInstance(self):
        return CountUniqueValuesAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input layer', [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, 'Field', parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any))
        self.addParameter(QgsProcessingParameterEnum(
            self.SORT, 'Sort by', options=_SORT, defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Counts', QgsProcessing.TypeVector))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_TXT, 'Text report (value | count)', 'Text files (*.txt)',
            optional=True, createByDefault=False))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_UNIQUE, 'Unique values'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field = self.parameterAsStrings(parameters, self.FIELD, context)[0]
        by_count = self.parameterAsEnum(parameters, self.SORT, context) == 1

        req = QgsFeatureRequest().setNoAttributes() \
            .setSubsetOfAttributes([field], source.fields())
        counts = core.count_values(source.getFeatures(req), field)
        ordered = core.sorted_counts(counts, by_count)
        feedback.pushInfo('{} unique value(s).'.format(len(ordered)))

        fields = QgsFields()
        fields.append(QgsField('value', QMetaType.Type.QString))
        fields.append(QgsField('count', QMetaType.Type.Int))
        sink, dest = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields, QgsWkbTypes.NoGeometry,
            source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        for value, count in ordered:
            f = QgsFeature(fields)
            f.setAttributes([value, count])
            sink.addFeature(f)

        result = {self.OUTPUT: dest, self.OUT_UNIQUE: len(ordered)}
        txt = self.parameterAsFileOutput(parameters, self.OUTPUT_TXT, context)
        if txt:
            core.write_txt(txt, counts, by_count)
            result[self.OUTPUT_TXT] = txt
        return result


class _KeywordBase(QgsProcessingAlgorithm):
    FIELD = 'FIELD'
    KEYWORDS = 'KEYWORDS'

    def group(self):
        return 'Owners analysis'

    def groupId(self):
        return 'owners_analysis'

    def tags(self):
        return ['owners', 'keywords', 'search', 'filter', 'მფლობელები']

    def _add_keyword_parameters(self):
        self.addParameter(QgsProcessingParameterString(
            self.KEYWORDS, 'Keywords (one per line)', multiLine=True))

    def _terms(self, parameters, context):
        terms = core.parse_terms(self.parameterAsString(parameters, self.KEYWORDS, context))
        if not terms:
            raise QgsProcessingException('Enter at least one keyword.')
        return terms


class ExtractByKeywordsAlgorithm(_KeywordBase):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    OUT_COUNT = 'COUNT'

    def name(self):
        return 'extract_by_keywords'

    def displayName(self):
        return 'Extract features by keywords'

    def shortHelpString(self):
        return (
            'Copies the features whose field contains at least one of the keywords '
            '(plain substring match, case-sensitive, one keyword per line) to a new '
            'layer. Works anywhere, including models and qgis_process.'
        )

    def createInstance(self):
        return ExtractByKeywordsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input layer', [QgsProcessing.TypeVector]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, 'Field to search', parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any))
        self._add_keyword_parameters()
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Matching features'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_COUNT, 'Matching features'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field = self.parameterAsStrings(parameters, self.FIELD, context)[0]
        terms = self._terms(parameters, context)

        sink, dest = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(), source.wkbType(),
            source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        total = source.featureCount()
        step = 100.0 / total if total else 0
        n = 0
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            val = feat[field]
            if not core._is_null(val) and any(t in str(val) for t in terms):
                sink.addFeature(feat)
                n += 1
            feedback.setProgress(int(i * step))
        feedback.pushInfo('{} feature(s) match.'.format(n))
        return {self.OUTPUT: dest, self.OUT_COUNT: n}


class SelectByKeywordsAlgorithm(_KeywordBase):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    OUT_COUNT = 'COUNT'

    def name(self):
        return 'select_by_keywords'

    def displayName(self):
        return 'Select features by keywords'

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def shortHelpString(self):
        return (
            'Selects, on the layer itself, the features whose field contains at least '
            'one of the keywords (plain substring match, case-sensitive, one keyword '
            'per line), like the search tab of the Owners Analyzer dialog. Replaces the '
            'current selection.'
        )

    def createInstance(self):
        return SelectByKeywordsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT, 'Layer'))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, 'Field to search', parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any))
        self._add_keyword_parameters()
        self.addOutput(QgsProcessingOutputMapLayer(self.OUTPUT, 'Layer'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_COUNT, 'Selected features'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field = self.parameterAsStrings(parameters, self.FIELD, context)[0]
        terms = self._terms(parameters, context)

        ids, matches = core.find_matches(layer.getFeatures(), field, terms)
        layer.selectByIds(ids)
        for term, count in sorted(matches.items(), key=lambda x: -x[1]):
            feedback.pushInfo('"{}": {}'.format(term, count))
        feedback.pushInfo('{} feature(s) selected.'.format(len(ids)))
        return {self.OUTPUT: layer.id(), self.OUT_COUNT: len(ids)}
