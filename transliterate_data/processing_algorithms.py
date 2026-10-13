# -*- coding: utf-8 -*-
"""Transliterate data folder — batch rename of Georgian names (Processing)."""
import os

from qgis.core import (
    Qgis,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputFolder,
    QgsProcessingOutputNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
)

from . import engine

_MODES = [
    'Preview only (no changes)',
    'Copy to a new folder, then rename in the copy',
    'Rename in place (changes the original data!)',
]
_PREVIEW, _COPY, _INPLACE = 0, 1, 2

_KIND_LABEL = {
    'shp': 'shapefile',
    'dbfile': 'database file',
    'layer': 'layer',
    'field': 'field',
}


class TransliterateFolderAlgorithm(QgsProcessingAlgorithm):
    FOLDER = 'FOLDER'
    MODE = 'MODE'
    COPY_TO = 'COPY_TO'
    RECURSIVE = 'RECURSIVE'
    SHP_FILES = 'SHP_FILES'
    DB_FILES = 'DB_FILES'
    LAYERS = 'LAYERS'
    FIELDS = 'FIELDS'
    OUT_PLANNED = 'PLANNED'
    OUT_RENAMED = 'RENAMED'
    OUT_FAILED = 'FAILED'
    OUT_FOLDER = 'OUTPUT_FOLDER'

    def name(self):
        return 'transliterate_folder'

    def displayName(self):
        return 'Transliterate data folder'

    def group(self):
        return 'Data preparation'

    def groupId(self):
        return 'data_preparation'

    def tags(self):
        return ['transliterate', 'rename', 'georgian', 'latin', 'shapefile', 'geopackage',
                'ქართული', 'ტრანსლიტერაცია']

    def shortHelpString(self):
        return (
            'Finds Georgian-named data in a folder and renames it to clean, '
            'filesystem- and SQL-safe Latin (national romanization; other characters '
            'become "_"): shapefile sets, database files (gpkg / sqlite / gdb), layers '
            'inside databases and field names.\n\n'
            'Mode "Preview only" (default) lists what would change and touches nothing. '
            '"Copy to a new folder" copies the whole tree first and renames in the copy '
            '(the target folder must not exist yet). "Rename in place" changes the '
            'original data - make sure no QGIS layer has the files open.'
        )

    def createInstance(self):
        return TransliterateFolderAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.FOLDER, 'Data folder',
            behavior=Qgis.ProcessingFileParameterBehavior.Folder))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODE, 'Mode', options=_MODES, defaultValue=_PREVIEW))
        self.addParameter(QgsProcessingParameterFile(
            self.COPY_TO, 'Copy to (new folder; used by the copy mode)',
            behavior=Qgis.ProcessingFileParameterBehavior.Folder, optional=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.RECURSIVE, 'Include sub-folders', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SHP_FILES, 'Rename shapefile sets', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DB_FILES, 'Rename database files (gpkg / sqlite / gdb)', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.LAYERS, 'Rename layers / tables inside databases', defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.FIELDS, 'Rename field names', defaultValue=True))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_PLANNED, 'Planned changes'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_RENAMED, 'Renamed'))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_FAILED, 'Failed'))
        self.addOutput(QgsProcessingOutputFolder(self.OUT_FOLDER, 'Folder with the result'))

    def checkParameterValues(self, parameters, context):
        folder = self.parameterAsFile(parameters, self.FOLDER, context)
        if not folder or not os.path.isdir(folder):
            return False, 'Data folder does not exist: {}'.format(folder)
        if self.parameterAsEnum(parameters, self.MODE, context) == _COPY:
            dest = self.parameterAsFile(parameters, self.COPY_TO, context)
            if not dest:
                return False, 'Choose the "Copy to" folder for the copy mode.'
            if os.path.exists(dest):
                return False, 'The "Copy to" folder already exists: {}'.format(dest)
        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        folder = self.parameterAsFile(parameters, self.FOLDER, context)
        mode = self.parameterAsEnum(parameters, self.MODE, context)
        opts = {
            'recursive': self.parameterAsBoolean(parameters, self.RECURSIVE, context),
            'shp_files': self.parameterAsBoolean(parameters, self.SHP_FILES, context),
            'db_files': self.parameterAsBoolean(parameters, self.DB_FILES, context),
            'layers': self.parameterAsBoolean(parameters, self.LAYERS, context),
            'fields': self.parameterAsBoolean(parameters, self.FIELDS, context),
        }

        actions = engine.scan(folder, recursive=opts['recursive'], opts=opts)
        feedback.pushInfo('{} change(s) planned.'.format(len(actions)))
        for act in actions:
            feedback.pushInfo('  {}: {}  ->  {}'.format(
                _KIND_LABEL.get(act['kind'], act['kind']), act['old'], act['new']))

        result = {self.OUT_PLANNED: len(actions), self.OUT_RENAMED: 0,
                  self.OUT_FAILED: 0, self.OUT_FOLDER: folder}
        if mode == _PREVIEW or not actions:
            if mode == _PREVIEW:
                feedback.pushInfo('Preview only - nothing was changed.')
            return result

        copy_to = None
        if mode == _COPY:
            copy_to = self.parameterAsFile(parameters, self.COPY_TO, context)

        total = len(actions)
        done = [0]

        def progress(_act, _err):
            done[0] += 1
            feedback.setProgress(int(100.0 * done[0] / total))

        try:
            res = engine.apply(folder, opts, copy_to=copy_to, progress=progress)
        except FileExistsError as exc:
            raise QgsProcessingException('Already exists: {}'.format(exc))

        for act, err in res['failed']:
            feedback.reportError('{} "{}": {}'.format(
                _KIND_LABEL.get(act['kind'], act['kind']), act['old'], err))
        feedback.pushInfo('Renamed {}, failed {}.'.format(res['ok'], len(res['failed'])))
        result[self.OUT_RENAMED] = res['ok']
        result[self.OUT_FAILED] = len(res['failed'])
        result[self.OUT_FOLDER] = res['root']
        return result
