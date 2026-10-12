"""QGIS Processing provider: the same photo tools as algorithms (Toolbox, Model Builder, qgis_process)."""
import os

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsField, QgsFields,
    QgsGeometry, QgsPointXY, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingOutputNumber, QgsProcessingParameterBoolean, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField, QgsProcessingParameterFile,
    QgsProcessingParameterEnum, QgsProcessingParameterNumber, QgsProcessingParameterString, QgsProcessingProvider,
    QgsSettings)

from . import core, export, geocode, i18n
from .layer_places import LayerLookup

WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
GROUP_ID = "photo_geotagger"


def _tr(key, *args):
    return i18n.t_lang(key, i18n.locale_lang(), *args)


def _load_engine_settings():
    settings = QgsSettings()
    core.CONFIG.update({
        "engine": settings.value("photo_geotagger/engine", "auto") or "auto",
        "exiftool": settings.value("photo_geotagger/exiftool", "") or "",
        "raw_embed": str(settings.value("photo_geotagger/raw_embed", "false")).lower() == "true"})


class _Base(QgsProcessingAlgorithm):
    ID = ""
    KEY = ""  # i18n key of the display name; the help text uses KEY + "_help"

    def name(self):
        return self.ID

    def displayName(self):
        return _tr(self.KEY)

    def group(self):
        return _tr("alg_group")

    def groupId(self):
        return GROUP_ID

    def shortHelpString(self):
        return _tr(self.KEY + "_help")

    def createInstance(self):
        return type(self)()

    # shared parameter helpers
    def _add_photos(self):
        self.addParameter(QgsProcessingParameterFile("PHOTOS", _tr("p_photos"),
                                                     behavior=QgsProcessingParameterFile.Behavior.Folder))
        self.addParameter(QgsProcessingParameterBoolean("RECURSIVE", _tr("p_recursive"), defaultValue=False))

    def _add_write_options(self):
        self.addParameter(QgsProcessingParameterBoolean("OVERWRITE", _tr("overwrite"), defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean("BACKUP", _tr("backup"), defaultValue=True))

    def _add_counts(self):
        for key, label in (("WRITTEN", "o_written"), ("SKIPPED", "o_skipped"), ("ERRORS", "o_errors")):
            self.addOutput(QgsProcessingOutputNumber(key, _tr(label)))

    def _photos(self, parameters, context):
        folder = self.parameterAsFile(parameters, "PHOTOS", context)
        photos = core.collect_photos([folder], self.parameterAsBool(parameters, "RECURSIVE", context))
        if not photos:
            raise QgsProcessingException(_tr("alg_no_photos"))
        return photos

    def _report_fields(self):
        fields = QgsFields()
        for name, kind in (("file", "QString"), ("path", "QString"), ("lat", "Double"), ("lon", "Double"),
                           ("status", "QString"), ("detail", "QString")):
            fields.append(QgsField(name, getattr(QMetaType.Type, kind)))
        return fields

    def _add_report_sink(self):
        self.addParameter(QgsProcessingParameterFeatureSink(
            "REPORT", _tr("o_report"), QgsProcessing.SourceType.VectorPoint, optional=True, createByDefault=False))

    def _run_tagging(self, photos, source, parameters, context, feedback):
        backup = self.parameterAsBool(parameters, "BACKUP", context)
        overwrite = self.parameterAsBool(parameters, "OVERWRITE", context)
        fields = self._report_fields()
        sink, dest = self.parameterAsSink(parameters, "REPORT", context, fields, Qgis.WkbType.Point, WGS84)
        counts = {"WRITTEN": 0, "SKIPPED": 0, "ERRORS": 0}
        total = max(len(photos), 1)
        for i, path in enumerate(photos):
            if feedback.isCanceled():
                break
            status, pos, detail = core.tag_photo(path, source, backup=backup, overwrite=overwrite)
            key = "WRITTEN" if status in ("ok", "ok_xmp") else ("ERRORS" if status == "error" else "SKIPPED")
            counts[key] += 1
            feedback.pushInfo("%s: %s %s" % (path, _tr("res_" + status), detail))
            if sink is not None:
                f = QgsFeature(fields)
                if pos:
                    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(pos[1], pos[0])))
                f.setAttributes([os.path.basename(path), path, pos[0] if pos else None, pos[1] if pos else None,
                                 status, detail])
                sink.addFeature(f)
            feedback.setProgress(100.0 * (i + 1) / total)
        result = dict(counts)
        if sink is not None:
            result["REPORT"] = dest
        return result


class PhotosToPoints(_Base):
    ID = "photos_to_points"
    KEY = "alg_photos_to_points"

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", _tr("o_photos"), QgsProcessing.SourceType.VectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        records = []
        photos = self._photos(parameters, context)
        total = max(len(photos), 1)
        for i, p in enumerate(photos):
            if feedback.isCanceled():
                break
            records += core.build_records([p])
            feedback.setProgress(100.0 * (i + 1) / total)
        fields = QgsFields()
        for name in export.FIELDS:
            fields.append(QgsField(name, QMetaType.Type.Double if name in export.REAL_FIELDS else QMetaType.Type.QString))
        sink, dest = self.parameterAsSink(parameters, "OUTPUT", context, fields, Qgis.WkbType.Point, WGS84)
        for r in records:
            f = QgsFeature(fields)
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(r["lon"], r["lat"])))
            f.setAttributes([r[k] for k in export.FIELDS])
            sink.addFeature(f)
        feedback.pushInfo(_tr("layer_added", len(records)))
        return {"OUTPUT": dest}


class GeotagFromGpx(_Base):
    ID = "geotag_from_gpx"
    KEY = "alg_geotag_gpx"

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addParameter(QgsProcessingParameterFile("GPX", _tr("p_gpx"), extension="gpx"))
        self.addParameter(QgsProcessingParameterNumber("UTC_OFFSET", _tr("utc_offset"),
                                                       QgsProcessingParameterNumber.Type.Double, 4.0))
        self.addParameter(QgsProcessingParameterNumber("SHIFT", _tr("shift"),
                                                       QgsProcessingParameterNumber.Type.Double, 0.0))
        self.addParameter(QgsProcessingParameterNumber("MAX_GAP", _tr("max_gap"),
                                                       QgsProcessingParameterNumber.Type.Double, 600.0, minValue=0))
        self._add_write_options()
        self._add_report_sink()
        self._add_counts()

    def processAlgorithm(self, parameters, context, feedback):
        photos = self._photos(parameters, context)
        try:
            source = core.load_source(
                "gpx", file=self.parameterAsFile(parameters, "GPX", context),
                utc_offset=self.parameterAsDouble(parameters, "UTC_OFFSET", context),
                shift=self.parameterAsDouble(parameters, "SHIFT", context),
                max_gap=self.parameterAsDouble(parameters, "MAX_GAP", context))
        except core.GeotagError as exc:
            raise QgsProcessingException(_tr("bad_source", exc))
        return self._run_tagging(photos, source, parameters, context, feedback)


class GeotagFromCsv(_Base):
    ID = "geotag_from_csv"
    KEY = "alg_geotag_csv"

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addParameter(QgsProcessingParameterFile("CSV", _tr("p_csv"), extension="csv"))
        self._add_write_options()
        self._add_report_sink()
        self._add_counts()

    def processAlgorithm(self, parameters, context, feedback):
        photos = self._photos(parameters, context)
        try:
            source = core.load_source("csv", file=self.parameterAsFile(parameters, "CSV", context))
        except core.GeotagError as exc:
            raise QgsProcessingException(_tr("bad_source", exc))
        return self._run_tagging(photos, source, parameters, context, feedback)


class GeotagFromLayer(_Base):
    ID = "geotag_from_layer"
    KEY = "alg_geotag_layer"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource("INPUT", _tr("p_layer"),
                                                              [QgsProcessing.SourceType.VectorPoint]))
        self.addParameter(QgsProcessingParameterField("PATH_FIELD", _tr("p_path_field"), "path", "INPUT",
                                                      QgsProcessingParameterField.DataType.String))
        self.addParameter(QgsProcessingParameterField("ALT_FIELD", _tr("p_alt_field"), None, "INPUT",
                                                      QgsProcessingParameterField.DataType.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterField("DIR_FIELD", _tr("p_dir_field"), None, "INPUT",
                                                      QgsProcessingParameterField.DataType.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterBoolean("BACKUP", _tr("backup"), defaultValue=True))
        self._add_counts()

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, "INPUT", context)
        path_field = self.parameterAsString(parameters, "PATH_FIELD", context)
        alt_field = self.parameterAsString(parameters, "ALT_FIELD", context)
        dir_field = self.parameterAsString(parameters, "DIR_FIELD", context)
        backup = self.parameterAsBool(parameters, "BACKUP", context)
        names = source.fields().names()
        for field in (path_field, alt_field, dir_field):
            if field and field not in names:
                raise QgsProcessingException(_tr("alg_bad_field", field))
        to_wgs = QgsCoordinateTransform(source.sourceCrs(), WGS84, context.transformContext())

        def number(feature, field):
            value = feature[field] if field else None
            return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

        counts = {"WRITTEN": 0, "SKIPPED": 0, "ERRORS": 0}
        total = max(source.featureCount(), 1)
        for i, f in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            path = f[path_field]
            if not isinstance(path, str) or not path or f.geometry().isNull():
                counts["SKIPPED"] += 1
                continue
            p = to_wgs.transform(QgsPointXY(f.geometry().vertexAt(0)))
            status, detail = core.set_position(path, p.y(), p.x(), number(f, alt_field), number(f, dir_field), backup)
            counts["WRITTEN" if status in ("ok", "ok_xmp") else ("ERRORS" if status == "error" else "SKIPPED")] += 1
            if status != "same":
                feedback.pushInfo("%s: %s %s" % (path, _tr("res_" + status), detail))
            feedback.setProgress(100.0 * (i + 1) / total)
        return counts


class RestoreOriginals(_Base):
    ID = "restore_originals"
    KEY = "alg_restore"

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addOutput(QgsProcessingOutputNumber("RESTORED", _tr("o_restored")))
        self.addOutput(QgsProcessingOutputNumber("SKIPPED", _tr("o_skipped")))
        self.addOutput(QgsProcessingOutputNumber("ERRORS", _tr("o_errors")))

    def processAlgorithm(self, parameters, context, feedback):
        counts = {"RESTORED": 0, "SKIPPED": 0, "ERRORS": 0}
        photos = self._photos(parameters, context)
        for i, path in enumerate(photos):
            if feedback.isCanceled():
                break
            status, detail = core.restore_photo(path)
            counts["RESTORED" if status in ("restored", "sidecar_removed") else
                   ("ERRORS" if status == "error" else "SKIPPED")] += 1
            feedback.pushInfo("%s: %s %s" % (path, _tr("res_" + status), detail))
            feedback.setProgress(100.0 * (i + 1) / max(len(photos), 1))
        return counts


class EstimateOffset(_Base):
    ID = "estimate_clock_offset"
    KEY = "alg_offset"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile("PHOTO", _tr("p_photo"),
                                                     behavior=QgsProcessingParameterFile.Behavior.File))
        self.addParameter(QgsProcessingParameterFile("GPX", _tr("p_gpx"), extension="gpx"))
        self.addParameter(QgsProcessingParameterNumber("LAT", _tr("p_true_lat"),
                                                       QgsProcessingParameterNumber.Type.Double, minValue=-90, maxValue=90))
        self.addParameter(QgsProcessingParameterNumber("LON", _tr("p_true_lon"),
                                                       QgsProcessingParameterNumber.Type.Double, minValue=-180, maxValue=180))
        for key, label in (("UTC_OFFSET", "o_utc"), ("SHIFT", "o_shift"), ("DISTANCE", "o_distance")):
            self.addOutput(QgsProcessingOutputNumber(key, _tr(label)))

    def processAlgorithm(self, parameters, context, feedback):
        photo = self.parameterAsFile(parameters, "PHOTO", context)
        taken = core.read_datetime(photo)
        if taken is None:
            raise QgsProcessingException(_tr("alg_no_time"))
        try:
            points = core.parse_gpx(self.parameterAsFile(parameters, "GPX", context))
        except (core.GeotagError, OSError, ValueError) as exc:
            raise QgsProcessingException(_tr("bad_source", exc))
        offset, shift, dist = core.estimate_offset(points, taken, self.parameterAsDouble(parameters, "LAT", context),
                                                   self.parameterAsDouble(parameters, "LON", context))
        feedback.pushInfo(_tr("estimate_done", offset, round(shift), round(dist)))
        return {"UTC_OFFSET": offset, "SHIFT": round(shift), "DISTANCE": round(dist)}


def _tally(counts, status):
    counts["WRITTEN" if status in ("ok", "ok_xmp") else ("ERRORS" if status == "error" else "SKIPPED")] += 1


class PlaceFromOsm(_Base):
    ID = "place_names_from_osm"
    KEY = "alg_place_osm"

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addParameter(QgsProcessingParameterEnum("LANGUAGE", _tr("p_language"), ["ქართული", "English"],
                                                     defaultValue=0 if i18n.locale_lang() == "ka" else 1))
        self.addParameter(QgsProcessingParameterString("URL", _tr("p_url"), defaultValue=geocode.PUBLIC_URL))
        self._add_write_options()
        self._add_counts()

    def processAlgorithm(self, parameters, context, feedback):
        photos = self._photos(parameters, context)
        lang = ("ka", "en")[self.parameterAsEnum(parameters, "LANGUAGE", context)]
        geocoder = geocode.Geocoder(lang, self.parameterAsString(parameters, "URL", context))
        overwrite = self.parameterAsBool(parameters, "OVERWRITE", context)
        backup = self.parameterAsBool(parameters, "BACKUP", context)
        counts = {"WRITTEN": 0, "SKIPPED": 0, "ERRORS": 0}
        for i, path in enumerate(photos):
            if feedback.isCanceled():
                break
            pos = core.read_gps(path)
            if not pos:
                status, detail = "no_gps", ""
            else:
                try:
                    place = geocoder.lookup(pos[0], pos[1])
                    status, detail = core.set_place(path, place, overwrite, backup) if place else ("no_place", "")
                except geocode.GeocodeError as exc:
                    status, detail = "error", str(exc)
            _tally(counts, status)
            feedback.pushInfo("%s: %s %s" % (path, _tr("res_" + status), detail))
            feedback.setProgress(100.0 * (i + 1) / max(len(photos), 1))
        return counts


class PlaceFromLayer(_Base):
    ID = "place_names_from_layer"
    KEY = "alg_place_layer"
    FIELDS = (("COUNTRY", "p_country_field", "country"), ("REGION", "p_region_field", "region"),
              ("CITY", "p_city_field", "city"), ("LOCATION", "p_location_field", "location"))

    def initAlgorithm(self, config=None):
        self._add_photos()
        self.addParameter(QgsProcessingParameterFeatureSource(
            "LAYER", _tr("p_layer"), [QgsProcessing.SourceType.VectorPolygon, QgsProcessing.SourceType.VectorPoint]))
        for key, label, _ in self.FIELDS:
            self.addParameter(QgsProcessingParameterField(key + "_FIELD", _tr(label), None, "LAYER",
                                                          QgsProcessingParameterField.DataType.Any, optional=True))
        self.addParameter(QgsProcessingParameterNumber("MAX_DISTANCE", _tr("p_max_distance"),
                                                       QgsProcessingParameterNumber.Type.Double, 100.0, minValue=0))
        self._add_write_options()
        self._add_counts()

    def processAlgorithm(self, parameters, context, feedback):
        photos = self._photos(parameters, context)
        source = self.parameterAsSource(parameters, "LAYER", context)
        mapping = {name: self.parameterAsString(parameters, key + "_FIELD", context) for key, _, name in self.FIELDS}
        names = source.fields().names()
        for field in mapping.values():
            if field and field not in names:
                raise QgsProcessingException(_tr("alg_bad_field", field))
        if not any(mapping.values()):
            raise QgsProcessingException(_tr("place_no_fields"))
        lookup = LayerLookup(source.getFeatures(), source.sourceCrs(), mapping, context.transformContext(),
                             self.parameterAsDouble(parameters, "MAX_DISTANCE", context))
        overwrite = self.parameterAsBool(parameters, "OVERWRITE", context)
        backup = self.parameterAsBool(parameters, "BACKUP", context)
        counts = {"WRITTEN": 0, "SKIPPED": 0, "ERRORS": 0}
        for i, path in enumerate(photos):
            if feedback.isCanceled():
                break
            pos = core.read_gps(path)
            if not pos:
                status, detail = "no_gps", ""
            else:
                place = lookup.lookup(pos[0], pos[1])
                status, detail = core.set_place(path, place, overwrite, backup) if place else ("no_place", "")
            _tally(counts, status)
            feedback.pushInfo("%s: %s %s" % (path, _tr("res_" + status), detail))
            feedback.setProgress(100.0 * (i + 1) / max(len(photos), 1))
        return counts


class PhotoGeotaggerProvider(QgsProcessingProvider):
    def id(self):
        return GROUP_ID

    def name(self):
        return _tr("provider_name")

    def longName(self):
        return self.name()

    def loadAlgorithms(self):
        _load_engine_settings()
        for cls in (PhotosToPoints, GeotagFromGpx, GeotagFromCsv, GeotagFromLayer, PlaceFromOsm, PlaceFromLayer,
                    RestoreOriginals, EstimateOffset):
            self.addAlgorithm(cls())
