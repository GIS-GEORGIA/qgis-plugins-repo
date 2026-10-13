# -*- coding: utf-8 -*-
"""Layer Cleaner as Processing algorithms. Both change the project, so they run on the
main thread and need a project (the open one in QGIS, or --project in qgis_process)."""
import re

from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterString,
    QgsProject,
)

from . import cleaner_core


def _project(context):
    return context.project() or QgsProject.instance()


class _ProjectAlgorithm(QgsProcessingAlgorithm):

    def group(self):
        return 'Project'

    def groupId(self):
        return 'project'

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading


class RemoveLayersAlgorithm(_ProjectAlgorithm):
    KEEP_NAMES = 'KEEP_NAMES'
    KEEP_LAYERS = 'KEEP_LAYERS'
    OUT_REMOVED = 'REMOVED'

    def name(self):
        return 'remove_layers'

    def displayName(self):
        return 'Remove layers from project (keep base layers)'

    def tags(self):
        return ['layers', 'clean', 'remove', 'project']

    def shortHelpString(self):
        return (
            'Removes every layer from the project except those whose name is listed '
            '(default: the two base layers, "Google Satellite Hybrid" and '
            '"OpenStreetMap") and any layers chosen under "Layers to keep".\n\n'
            'WARNING: the removal cannot be undone from here. Leave both keep options '
            'empty only if you really want to empty the project.'
        )

    def createInstance(self):
        return RemoveLayersAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(
            self.KEEP_NAMES, 'Layer names to keep (one per line)', multiLine=True,
            defaultValue='\n'.join(cleaner_core.KEEP_NAMES), optional=True))
        self.addParameter(QgsProcessingParameterMultipleLayers(
            self.KEEP_LAYERS, 'Layers to keep', optional=True))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_REMOVED, 'Layers removed'))

    def processAlgorithm(self, parameters, context, feedback):
        project = _project(context)
        names = [n.strip() for n in re.split(
            r'[\r\n]+', self.parameterAsString(parameters, self.KEEP_NAMES, context) or '')
            if n.strip()]
        keep_ids = [lyr.id() for lyr in
                    self.parameterAsLayerList(parameters, self.KEEP_LAYERS, context)]
        ids = cleaner_core.layers_to_remove(project, names, keep_ids)
        for lid in ids:
            lyr = project.mapLayer(lid)
            feedback.pushInfo('Removing: {}'.format(lyr.name() if lyr else lid))
        cleaner_core.remove_layers(ids, project)
        feedback.pushInfo('Removed {} layer(s).'.format(len(ids)))
        return {self.OUT_REMOVED: len(ids)}


class AddBaseLayersAlgorithm(_ProjectAlgorithm):
    OUT_ADDED = 'ADDED'

    def name(self):
        return 'add_base_layers'

    def displayName(self):
        return 'Add base layers (Google Satellite Hybrid, OpenStreetMap)'

    def tags(self):
        return ['basemap', 'google', 'osm', 'satellite', 'xyz']

    def shortHelpString(self):
        return ('Adds the "Google Satellite Hybrid" and "OpenStreetMap" XYZ tile layers '
                'to the project unless a layer with the same name already exists. '
                'Needs internet access to validate the tile services.')

    def createInstance(self):
        return AddBaseLayersAlgorithm()

    def initAlgorithm(self, config=None):
        self.addOutput(QgsProcessingOutputString(self.OUT_ADDED, 'Added layers'))

    def processAlgorithm(self, parameters, context, feedback):
        project = _project(context)
        added = cleaner_core.add_base_layers(project)
        feedback.pushInfo('Added: {}'.format(', '.join(added) if added else 'nothing'))
        present = {lyr.name() for lyr in project.mapLayers().values()}
        if not set(cleaner_core.KEEP_NAMES) <= present:
            raise QgsProcessingException(
                'Some base layers could not be created (no network?).')
        return {self.OUT_ADDED: ', '.join(added)}
