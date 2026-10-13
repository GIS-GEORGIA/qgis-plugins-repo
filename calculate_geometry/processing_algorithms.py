# -*- coding: utf-8 -*-
"""Calculate geometry — write one geometry property into a field (Processing)."""
from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterString,
    QgsProject,
    QgsWkbTypes,
)

from .geometry_calculator import (
    GeometryCalculator,
    Method,
    POINT_PROPERTIES,
    LINE_PROPERTIES,
    POLYGON_PROPERTIES,
    properties_for_geometry,
)

_METHODS = [
    ('Cartesian — layer CRS', Method.CARTESIAN_LAYER_CRS),
    ('Cartesian — selected CRS', Method.CARTESIAN_TARGET_CRS),
    ('Ellipsoidal (geodesic, project ellipsoid)', Method.ELLIPSOIDAL),
]

_DU = Qgis.DistanceUnit
_AU = Qgis.AreaUnit
_DISTANCE_UNITS = [
    ('Meters', _DU.Meters), ('Kilometers', _DU.Kilometers), ('Feet', _DU.Feet),
    ('Miles', _DU.Miles), ('Nautical miles', _DU.NauticalMiles), ('Degrees', _DU.Degrees),
]
_AREA_UNITS = [
    ('Square meters', _AU.SquareMeters), ('Square kilometers', _AU.SquareKilometers),
    ('Hectares', _AU.Hectares), ('Square feet', _AU.SquareFeet),
    ('Square miles', _AU.SquareMiles), ('Acres', _AU.Acres),
]

_VARIANT = {
    'double': QMetaType.Type.Double,
    'int': QMetaType.Type.Int,
    'string': QMetaType.Type.QString,
}


def _property_options():
    """[(key, label)] over all geometry types, labelled with where each applies."""
    where = {}
    labels = {}
    for tag, props in (('point', POINT_PROPERTIES), ('line', LINE_PROPERTIES),
                       ('polygon', POLYGON_PROPERTIES)):
        for key, (label, _k, _t) in props.items():
            where.setdefault(key, []).append(tag)
            labels.setdefault(key, label)
    return [(k, '{}  [{}]'.format(labels[k], '/'.join(where[k]))) for k in where]


_PROPS = _property_options()


class _CrsHolder:
    """Minimal stand-in for the layer argument of GeometryCalculator."""

    def __init__(self, crs):
        self._crs = crs

    def crs(self):
        return self._crs


class _ProjectShim:
    """Project view for GeometryCalculator with a guaranteed ellipsoid.

    An empty project (qgis_process, scripts, models run outside a project) has the
    ellipsoid "NONE", which would silently make "Ellipsoidal" measure in degrees.
    """

    def __init__(self, project, ellipsoid):
        self._project = project
        self._ellipsoid = ellipsoid

    def transformContext(self):
        return self._project.transformContext()

    def ellipsoid(self):
        return self._ellipsoid


class CalculateGeometryAlgorithm(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    PROPERTY = 'PROPERTY'
    FIELD_NAME = 'FIELD_NAME'
    METHOD = 'METHOD'
    CRS = 'CRS'
    DISTANCE_UNIT = 'DISTANCE_UNIT'
    AREA_UNIT = 'AREA_UNIT'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'calculate_geometry'

    def displayName(self):
        return 'Calculate geometry'

    def group(self):
        return 'Vector geometry'

    def groupId(self):
        return 'vector_geometry'

    def tags(self):
        return ['geometry', 'area', 'length', 'perimeter', 'coordinates', 'field', 'calculate']

    def shortHelpString(self):
        return (
            'Writes one geometry property (area, perimeter, length, coordinates, vertex '
            'counts, bounding box ...) into a field, in the unit and measuring method of '
            'your choice. No expression needed.\n\n'
            'The property must fit the layer geometry type (shown in brackets). If the '
            'field exists its values are overwritten, otherwise it is created with a '
            'matching type. Chain several steps in a model to fill several fields.\n\n'
            '"Cartesian - selected CRS" needs the CRS parameter; "Ellipsoidal" uses the '
            'project ellipsoid (or the default one when run outside a project).'
        )

    def createInstance(self):
        return CalculateGeometryAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input layer', [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterEnum(
            self.PROPERTY, 'Geometry property', options=[lbl for _k, lbl in _PROPS],
            defaultValue=0))
        self.addParameter(QgsProcessingParameterString(
            self.FIELD_NAME, 'Target field (existing or new)', defaultValue='geom_val'))
        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD, 'Calculate using', options=[lbl for lbl, _m in _METHODS],
            defaultValue=2))
        self.addParameter(QgsProcessingParameterCrs(
            self.CRS, 'CRS (for "Cartesian - selected CRS")', optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.DISTANCE_UNIT, 'Distance unit (length / perimeter)',
            options=[lbl for lbl, _u in _DISTANCE_UNITS], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.AREA_UNIT, 'Area unit (area)',
            options=[lbl for lbl, _u in _AREA_UNITS], defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Output layer'))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        prop_key = _PROPS[self.parameterAsEnum(parameters, self.PROPERTY, context)][0]
        field_name = self.parameterAsString(parameters, self.FIELD_NAME, context).strip()
        if not field_name:
            raise QgsProcessingException('Target field name is empty.')
        method = _METHODS[self.parameterAsEnum(parameters, self.METHOD, context)][1]

        props = properties_for_geometry(QgsWkbTypes.geometryType(source.wkbType()))
        if prop_key not in props:
            raise QgsProcessingException(
                'Property "{}" does not apply to the geometry type of this layer.'
                .format(prop_key))
        _label, unit_kind, value_type = props[prop_key]

        target_crs = QgsCoordinateReferenceSystem()
        if method == Method.CARTESIAN_TARGET_CRS:
            target_crs = self.parameterAsCrs(parameters, self.CRS, context)
            if not target_crs.isValid():
                raise QgsProcessingException(
                    'Choose a CRS for "Cartesian - selected CRS".')

        fields = source.fields()
        idx = fields.lookupField(field_name)
        if idx < 0:
            fields.append(QgsField(field_name, _VARIANT[value_type]))
            idx = fields.count() - 1

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields, source.wkbType(), source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        project = context.project() or QgsProject.instance()
        shim = project
        if method == Method.ELLIPSOIDAL:
            ellipsoid = project.ellipsoid()
            if not ellipsoid or ellipsoid == 'NONE':
                ellipsoid = source.sourceCrs().ellipsoidAcronym() or 'EPSG:7030'
                feedback.pushInfo('Project has no ellipsoid; using {}.'.format(ellipsoid))
            shim = _ProjectShim(project, ellipsoid)
        calc = GeometryCalculator(_CrsHolder(source.sourceCrs()), method, target_crs, shim)
        if unit_kind == 'distance':
            calc.set_output_units(distance_unit=_DISTANCE_UNITS[
                self.parameterAsEnum(parameters, self.DISTANCE_UNIT, context)][1])
        elif unit_kind == 'area':
            calc.set_output_units(area_unit=_AREA_UNITS[
                self.parameterAsEnum(parameters, self.AREA_UNIT, context)][1])

        total = source.featureCount()
        step = 100.0 / total if total else 0
        n = fields.count()
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            attrs = list(feat.attributes())
            attrs.extend([None] * (n - len(attrs)))
            attrs[idx] = calc.value(feat, prop_key)
            out = QgsFeature(fields)
            out.setGeometry(feat.geometry())
            out.setAttributes(attrs)
            sink.addFeature(out)
            feedback.setProgress(int(i * step))
        return {self.OUTPUT: dest_id}
