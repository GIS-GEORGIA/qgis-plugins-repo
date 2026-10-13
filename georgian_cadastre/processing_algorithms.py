# -*- coding: utf-8 -*-
"""Georgian Cadastre as Processing algorithms (Toolbox, Model Builder, qgis_process).

Network access goes through ``qgis_net.qgis_fetch`` (proxy-aware), the same fetcher
the dialog uses. ``FETCH`` can be replaced in tests to run offline.
"""
import re

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterPoint,
    QgsProcessingParameterString,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QMetaType

from . import cadastre_core, napr_client
from .qgis_net import qgis_fetch

FETCH = None  # tests may inject an offline fetcher


def _fetch():
    return FETCH or qgis_fetch


_CRS_CHOICES = [
    'Auto (UTM zone of the first parcel)',
    'UTM 38N (EPSG:32638)',
    'UTM 37N (EPSG:32637)',
    'WGS 84 (EPSG:4326)',
    'Web Mercator (EPSG:3857)',
]
_CRS_EPSG = [None, 32638, 32637, 4326, 3857]

_CODE_SPLIT = re.compile(r'[\s,;]+')


def _output_fields(with_distance=False):
    fields = cadastre_core._fields()
    if with_distance:
        fields.append(QgsField('distance_m', QMetaType.Type.Double))
    return fields


def _resolve(match, with_info):
    """Geometry (+ optional info) for one search/reverse match."""
    fetch = _fetch()
    feats = napr_client.fetch_features(match['lbl'], fetch=fetch)
    info = None
    if with_info:
        try:
            info = napr_client.fetch_info(match['lbl'], fetch=fetch)
        except napr_client.NaprError:
            info = None
    return feats, info


def _add_parcels(sink, fields, feats, code, address, epsg, info, ctx, extra=None):
    n = 0
    for f in cadastre_core.make_features(feats, code, address, epsg, fields, info,
                                         transform_context=ctx, extra=extra):
        geom = f.geometry()
        geom.convertToMultiType()
        f.setGeometry(geom)
        sink.addFeature(f)
        n += 1
    return n


def _target_epsg(choice, first_wkt):
    epsg = _CRS_EPSG[choice]
    if epsg is not None:
        return epsg
    return cadastre_core.auto_zone_epsg(cadastre_core.geometry_from_wkt(first_wkt))


class FetchParcelsAlgorithm(QgsProcessingAlgorithm):
    CODES = 'CODES'
    TABLE = 'TABLE'
    CODE_FIELD = 'CODE_FIELD'
    CRS = 'CRS'
    WITH_INFO = 'WITH_INFO'
    OUTPUT = 'OUTPUT'
    OUT_FAILED = 'FAILED'

    def name(self):
        return 'fetch_parcels'

    def displayName(self):
        return 'Fetch parcels by cadastral code'

    def group(self):
        return 'Cadastre'

    def groupId(self):
        return 'cadastre'

    def tags(self):
        return ['cadastre', 'parcel', 'georgia', 'napr', 'საკადასტრო', 'ნაკვეთი']

    def shortHelpString(self):
        return (
            'Downloads parcel polygons from the public Georgian cadastre service by '
            'cadastral code (e.g. 38.10.42.107). Give codes in the text box '
            '(separated by new lines, commas or spaces), and/or a table with a code '
            'field. Output: one polygon per returned geometry row, with true ground '
            'area and perimeter (measured in UTM, whatever the output CRS), the '
            'official area and parcel type if "Include attributes" is on.\n\n'
            'Codes that are not found are reported as warnings and counted in the '
            '"Failed" output; the run continues. Needs internet access; the service '
            'is run by a third party and is sometimes unavailable.'
        )

    def createInstance(self):
        return FetchParcelsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(
            self.CODES, 'Cadastral codes', multiLine=True, optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TABLE, 'Table with codes', [QgsProcessing.TypeVector], optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.CODE_FIELD, 'Code field', parentLayerParameterName=self.TABLE,
            type=QgsProcessingParameterField.Any, optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.CRS, 'Output CRS', options=_CRS_CHOICES, defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WITH_INFO, 'Include attributes (official area, parcel type, status)',
            defaultValue=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Parcels', QgsProcessing.TypeVectorPolygon))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_FAILED, 'Codes not fetched'))

    def _codes(self, parameters, context):
        codes = [c for c in _CODE_SPLIT.split(
            self.parameterAsString(parameters, self.CODES, context) or '') if c]
        table = self.parameterAsSource(parameters, self.TABLE, context)
        if table is not None:
            field = self.parameterAsStrings(parameters, self.CODE_FIELD, context)
            if not field:
                raise QgsProcessingException('Choose the code field of the table.')
            for feat in table.getFeatures():
                val = feat[field[0]]
                if val is not None and str(val).strip():
                    codes.append(str(val).strip())
        seen, out = set(), []
        for c in codes:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def processAlgorithm(self, parameters, context, feedback):
        codes = self._codes(parameters, context)
        if not codes:
            raise QgsProcessingException('No cadastral codes given.')
        with_info = self.parameterAsBoolean(parameters, self.WITH_INFO, context)
        choice = self.parameterAsEnum(parameters, self.CRS, context)

        fields = _output_fields()
        sink = dest = None
        epsg = None
        failed = 0
        total = len(codes)
        for i, code in enumerate(codes):
            if feedback.isCanceled():
                break
            try:
                matches = napr_client.search(code, fetch=_fetch())
                if not matches:
                    raise napr_client.NaprError('err_not_found', code)
                match = matches[0]
                feats, info = _resolve(match, with_info)
                if sink is None:
                    epsg = _target_epsg(choice, feats[0]['wkt'])
                    sink, dest = self.parameterAsSink(
                        parameters, self.OUTPUT, context, fields,
                        QgsWkbTypes.MultiPolygon,
                        QgsCoordinateReferenceSystem('EPSG:{}'.format(epsg)))
                    if sink is None:
                        raise QgsProcessingException(
                            self.invalidSinkError(parameters, self.OUTPUT))
                n = _add_parcels(sink, fields, feats, match['code'], match['address'],
                                 epsg, info, context.transformContext())
                feedback.pushInfo('{}: {} geometry row(s)'.format(code, n))
            except napr_client.NaprError as exc:
                failed += 1
                feedback.pushWarning('{}: {}'.format(code, exc))
            feedback.setProgress(int(100.0 * (i + 1) / total))

        if sink is None:  # nothing fetched: still hand back an (empty) layer
            sink, dest = self.parameterAsSink(
                parameters, self.OUTPUT, context, fields, QgsWkbTypes.MultiPolygon,
                QgsCoordinateReferenceSystem('EPSG:{}'.format(
                    _CRS_EPSG[choice] or cadastre_core.ZONE_38N)))
            feedback.reportError('No parcel could be fetched.')
        return {self.OUTPUT: dest, self.OUT_FAILED: failed}


class ParcelsNearPointAlgorithm(QgsProcessingAlgorithm):
    POINT = 'POINT'
    RADIUS = 'RADIUS'
    LIMIT = 'LIMIT'
    CRS = 'CRS'
    WITH_INFO = 'WITH_INFO'
    OUTPUT = 'OUTPUT'

    def name(self):
        return 'parcels_near_point'

    def displayName(self):
        return 'Fetch parcels near a point'

    def group(self):
        return 'Cadastre'

    def groupId(self):
        return 'cadastre'

    def tags(self):
        return ['cadastre', 'parcel', 'reverse', 'georgia', 'საკადასტრო']

    def shortHelpString(self):
        return (
            'Finds cadastral parcels within a radius of a point (reverse lookup in the '
            'public cadastre service) and downloads their geometry. The point can be '
            'in any CRS. Adds a distance_m field with the distance reported by the '
            'service. Needs internet access.'
        )

    def createInstance(self):
        return ParcelsNearPointAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterPoint(self.POINT, 'Point'))
        self.addParameter(QgsProcessingParameterNumber(
            self.RADIUS, 'Search radius (m)', QgsProcessingParameterNumber.Integer,
            defaultValue=50, minValue=1, maxValue=2000))
        self.addParameter(QgsProcessingParameterNumber(
            self.LIMIT, 'Maximum number of parcels', QgsProcessingParameterNumber.Integer,
            defaultValue=8, minValue=1, maxValue=50))
        self.addParameter(QgsProcessingParameterEnum(
            self.CRS, 'Output CRS', options=_CRS_CHOICES, defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WITH_INFO, 'Include attributes (official area, parcel type, status)',
            defaultValue=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Parcels', QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):
        wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
        pt = self.parameterAsPoint(parameters, self.POINT, context, wgs84)
        radius = self.parameterAsInt(parameters, self.RADIUS, context)
        limit = self.parameterAsInt(parameters, self.LIMIT, context)
        with_info = self.parameterAsBoolean(parameters, self.WITH_INFO, context)
        choice = self.parameterAsEnum(parameters, self.CRS, context)

        try:
            matches = napr_client.reverse(pt.x(), pt.y(), radius=radius, limit=limit,
                                          fetch=_fetch())
        except napr_client.NaprError as exc:
            raise QgsProcessingException(str(exc))
        feedback.pushInfo('{} parcel(s) found near {:.6f}, {:.6f}'.format(
            len(matches), pt.x(), pt.y()))

        fields = _output_fields(with_distance=True)
        sink = dest = None
        epsg = None
        for i, match in enumerate(matches):
            if feedback.isCanceled():
                break
            try:
                feats, info = _resolve(match, with_info)
            except napr_client.NaprError as exc:
                feedback.pushWarning('{}: {}'.format(match['code'], exc))
                continue
            if sink is None:
                epsg = _target_epsg(choice, feats[0]['wkt'])
                sink, dest = self.parameterAsSink(
                    parameters, self.OUTPUT, context, fields, QgsWkbTypes.MultiPolygon,
                    QgsCoordinateReferenceSystem('EPSG:{}'.format(epsg)))
                if sink is None:
                    raise QgsProcessingException(
                        self.invalidSinkError(parameters, self.OUTPUT))
            _add_parcels(sink, fields, feats, match['code'], match['address'], epsg,
                         info, context.transformContext(), extra=[match.get('distance')])
            feedback.setProgress(int(100.0 * (i + 1) / len(matches)))

        if sink is None:
            sink, dest = self.parameterAsSink(
                parameters, self.OUTPUT, context, fields, QgsWkbTypes.MultiPolygon,
                QgsCoordinateReferenceSystem('EPSG:{}'.format(
                    _CRS_EPSG[choice] or cadastre_core.ZONE_38N)))
            feedback.reportError('No parcel found.')
        return {self.OUTPUT: dest}
