# -*- coding: utf-8 -*-
"""Add basemap - XYZ tile layer at the bottom of the project (Processing)."""
from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputMapLayer,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProject,
)

from .load_basemap import insert_at_bottom, make_xyz_layer

_PRESETS = [
    ('OpenStreetMap', 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'),
    ('Google Satellite Hybrid',
     'https://mt1.google.com/vt/lyrs=y%26x={x}%26y={y}%26z={z}'),
    ('Custom XYZ URL', ''),
]


class AddBasemapAlgorithm(QgsProcessingAlgorithm):
    BASEMAP = 'BASEMAP'
    URL = 'URL'
    NAME = 'NAME'
    ZMAX = 'ZMAX'
    SET_CRS = 'SET_CRS'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'add_basemap'

    def displayName(self):
        return 'Add basemap'

    def group(self):
        return 'Project'

    def groupId(self):
        return 'project'

    def tags(self):
        return ['basemap', 'xyz', 'tiles', 'osm', 'google']

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def shortHelpString(self):
        return (
            'Adds an XYZ tile basemap (OpenStreetMap, Google Satellite Hybrid or your '
            'own URL with {x} {y} {z}) at the bottom of the layer tree. A layer with '
            'the same name that is already in the project is reused. Optionally sets '
            'the project CRS to the basemap CRS (Web Mercator).'
        )

    def createInstance(self):
        return AddBasemapAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.BASEMAP, 'Basemap', options=[p[0] for p in _PRESETS], defaultValue=0))
        self.addParameter(QgsProcessingParameterString(
            self.URL, 'Custom XYZ URL (for "Custom XYZ URL")', optional=True))
        self.addParameter(QgsProcessingParameterString(
            self.NAME, 'Layer name (empty = preset name)', optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.ZMAX, 'Maximum zoom', QgsProcessingParameterNumber.Integer,
            defaultValue=19, minValue=0, maxValue=24))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SET_CRS, 'Set the project CRS to the basemap CRS (EPSG:3857)',
            defaultValue=False))
        self.addOutput(QgsProcessingOutputMapLayer(self.OUTPUT, 'Basemap layer'))

    def processAlgorithm(self, parameters, context, feedback):
        project = context.project() or QgsProject.instance()
        label, url = _PRESETS[self.parameterAsEnum(parameters, self.BASEMAP, context)]
        if not url:
            url = (self.parameterAsString(parameters, self.URL, context) or '').strip()
            if not all(t in url for t in ('{x}', '{y}', '{z}')):
                raise QgsProcessingException(
                    'Custom XYZ URL must contain {x}, {y} and {z}.')
        name = (self.parameterAsString(parameters, self.NAME, context) or '').strip() \
            or (label if url and label != 'Custom XYZ URL' else 'XYZ basemap')
        zmax = self.parameterAsInt(parameters, self.ZMAX, context)

        for lyr in project.mapLayers().values():
            if lyr.name() == name:
                feedback.pushInfo('Layer "{}" already in the project.'.format(name))
                return {self.OUTPUT: lyr.id()}

        layer = make_xyz_layer(url, name, zmax=zmax)
        if not layer.isValid():
            raise QgsProcessingException('Invalid basemap layer: {}'.format(url))
        if self.parameterAsBoolean(parameters, self.SET_CRS, context):
            project.setCrs(layer.crs())
        insert_at_bottom(layer, project)
        feedback.pushInfo('Added "{}".'.format(name))
        return {self.OUTPUT: layer.id()}
