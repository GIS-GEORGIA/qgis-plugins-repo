# -*- coding: utf-8 -*-
"""GIS Georgia Hub as Processing algorithms (Toolbox, Model Builder, qgis_process, Python).

For automation: no confirmation dialogs, so the safety lives in the checks - only plugins
that are in the *signed* catalog, downloads from plugins.qgis.ge over HTTPS, SHA-256 verified,
a QGIS-version check, and the Hub itself is never touched (use the Plugin Manager for it).
Blocking network calls on the main thread (these algorithms are not threaded).
"""
import os

from qgis import utils
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputBoolean,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterString,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QMetaType

from . import catalog, installer_core, signing
from .controller import CATALOG_URL

FETCH = None  # tests inject an offline fetcher: fn(url) -> bytes


def _fetch(url):
    return (FETCH or installer_core.download)(url)


def _cache_path():
    return os.path.join(QgsApplication.qgisSettingsDirPath(), "gis_georgia_hub", "catalog.json")


def load_catalog(refresh: bool, feedback) -> list:
    """The verified catalog's plugin list (downloads it when asked or when none is cached)."""
    path = _cache_path()
    doc = None if refresh else catalog.load_cache(path, signing.verify_catalog)
    if doc is None:
        try:
            text, sig = catalog.fetch_verified(_fetch, CATALOG_URL, signing.verify_catalog)
            doc = catalog.parse_catalog(text)
        except signing.SignatureError as exc:
            raise QgsProcessingException("Catalog rejected: {}".format(exc))
        except Exception as exc:  # noqa: BLE001
            raise QgsProcessingException("Could not load the catalog: {}".format(exc))
        catalog.save_cache(path, text, sig)
        feedback.pushInfo("Catalog loaded and signature verified.")
    return doc["plugins"]


def _qgis_version() -> str:
    return Qgis.version().split("-")[0]


def _find(plugins: list, plugin_id: str) -> dict:
    wanted = plugin_id.strip().lower()
    for p in plugins:
        if wanted in (p["id"].lower(), p["catalog_id"].lower()):
            return p
    raise QgsProcessingException("'{}' is not a GIS GEORGIA plugin in the catalog. Known: {}".format(
        plugin_id, ", ".join(sorted(p["id"] for p in plugins))))


def _install(entry: dict, feedback) -> installer_core.InstallResult:
    data = _fetch(entry["download"]["url"])
    return installer_core.install_zip(
        data, expected_id=entry["id"], expected_sha256=entry["download"]["sha256"],
        activate=utils.iface is not None)


class _Base(QgsProcessingAlgorithm):
    REFRESH = "REFRESH"

    def group(self):
        return "GIS Georgia Hub"

    def groupId(self):
        return "gis_georgia_hub"

    def flags(self):
        return super().flags() | Qgis.ProcessingAlgorithmFlag.NoThreading

    def _add_refresh(self):
        self.addParameter(QgsProcessingParameterBoolean(
            self.REFRESH, "Download the catalog first (otherwise the saved, verified copy is used)",
            defaultValue=True))


class InstallPluginAlgorithm(_Base):
    PLUGIN = "PLUGIN"
    ACTION = "ACTION"
    OUT_VERSION = "VERSION"
    OUT_CHANGED = "CHANGED"
    OUT_STARTED = "STARTED"

    def name(self):
        return "install_plugin"

    def displayName(self):
        return "Install, update or uninstall a GIS GEORGIA plugin"

    def tags(self):
        return ["install", "update", "uninstall", "plugin", "gis georgia"]

    def shortHelpString(self):
        return (
            "Installs (or updates to the catalog version) or uninstalls one plugin from the "
            "signed GIS GEORGIA catalog, e.g. calculate_geometry. Nothing is installed that is "
            "not in the catalog, the catalog signature and the file checksum are verified, and "
            "the Hub itself is never changed. There is no confirmation dialog - this is for "
            "scripts and models.\n\nOutside the QGIS window (qgis_process) the files are put in "
            "place but the plugin is not started; it starts with the next QGIS."
        )

    def createInstance(self):
        return InstallPluginAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterString(
            self.PLUGIN, "Plugin id (folder name, e.g. calculate_geometry)"))
        self.addParameter(QgsProcessingParameterEnum(
            self.ACTION, "Action", options=["Install or update", "Uninstall"], defaultValue=0))
        self._add_refresh()
        self.addOutput(QgsProcessingOutputString(self.OUT_VERSION, "Installed version"))
        self.addOutput(QgsProcessingOutputBoolean(self.OUT_CHANGED, "Something changed"))
        self.addOutput(QgsProcessingOutputBoolean(self.OUT_STARTED, "Plugin is running"))

    def processAlgorithm(self, parameters, context, feedback):
        plugins = load_catalog(self.parameterAsBoolean(parameters, self.REFRESH, context), feedback)
        entry = _find(plugins, self.parameterAsString(parameters, self.PLUGIN, context))
        if entry["id"] == catalog.SELF_ID:
            raise QgsProcessingException("The Hub does not change itself: use the QGIS Plugin Manager.")
        uninstall = self.parameterAsEnum(parameters, self.ACTION, context) == 1
        have = installer_core.installed_version(entry["id"])

        if uninstall:
            changed = installer_core.uninstall(entry["id"])
            feedback.pushInfo("{} removed.".format(entry["name"]) if changed
                              else "{} was not installed.".format(entry["name"]))
            return {self.OUT_VERSION: "", self.OUT_CHANGED: changed, self.OUT_STARTED: False}

        if have is None and not catalog.qgis_compatible(entry, _qgis_version()):
            raise QgsProcessingException("{} {} does not support QGIS {} (needs {} - {}).".format(
                entry["name"], entry["version"], _qgis_version(), entry["qgis_min"], entry["qgis_max"]))
        if have is not None and catalog.compare_versions(entry["version"], have) <= 0:
            feedback.pushInfo("{} {} is already up to date.".format(entry["name"], have))
            return {self.OUT_VERSION: have, self.OUT_CHANGED: False,
                    self.OUT_STARTED: utils.isPluginLoaded(entry["id"])}
        try:
            res = _install(entry, feedback)
        except installer_core.InstallError as exc:
            raise QgsProcessingException(str(exc))
        feedback.pushInfo("{} {} installed{}.".format(
            entry["name"], res.version, " (was {})".format(res.previous_version) if res.previous_version else ""))
        return {self.OUT_VERSION: res.version, self.OUT_CHANGED: True, self.OUT_STARTED: res.started}


class UpdatePluginsAlgorithm(_Base):
    DRY_RUN = "DRY_RUN"
    OUT_COUNT = "UPDATED"
    OUT_NAMES = "NAMES"

    def name(self):
        return "update_plugins"

    def displayName(self):
        return "Update all installed GIS GEORGIA plugins"

    def tags(self):
        return ["update", "plugins", "gis georgia"]

    def shortHelpString(self):
        return (
            "Updates every installed GIS GEORGIA plugin that has a newer version in the signed "
            "catalog (the Hub itself is excluded). Tick 'Only list' to see what would be "
            "updated without changing anything. Checksums and the catalog signature are verified; "
            "no confirmation dialog - this is for scripts and models."
        )

    def createInstance(self):
        return UpdatePluginsAlgorithm()

    def initAlgorithm(self, config=None):
        self._add_refresh()
        self.addParameter(QgsProcessingParameterBoolean(
            self.DRY_RUN, "Only list what would be updated", defaultValue=False))
        self.addOutput(QgsProcessingOutputNumber(self.OUT_COUNT, "Plugins updated (or pending)"))
        self.addOutput(QgsProcessingOutputString(self.OUT_NAMES, "Plugin ids"))

    def processAlgorithm(self, parameters, context, feedback):
        plugins = load_catalog(self.parameterAsBoolean(parameters, self.REFRESH, context), feedback)
        installed = {p["id"]: v for p in plugins if (v := installer_core.installed_version(p["id"]))}
        pending = catalog.updates(plugins, installed, _qgis_version())
        dry = self.parameterAsBoolean(parameters, self.DRY_RUN, context)
        done = []
        for i, entry in enumerate(pending):
            if feedback.isCanceled():
                break
            line = "{}: {} -> {}".format(entry["id"], installed[entry["id"]], entry["version"])
            if dry:
                feedback.pushInfo("would update " + line)
                done.append(entry["id"])
                continue
            feedback.pushInfo("updating " + line)
            try:
                _install(entry, feedback)
                done.append(entry["id"])
            except installer_core.InstallError as exc:
                feedback.reportError("{}: {}".format(entry["id"], exc))
            feedback.setProgress(int(100 * (i + 1) / len(pending)))
        if not pending:
            feedback.pushInfo("Everything is up to date.")
        return {self.OUT_COUNT: len(done), self.OUT_NAMES: ", ".join(done)}


class ListCatalogAlgorithm(_Base):
    OUTPUT = "OUTPUT"

    def name(self):
        return "list_catalog"

    def displayName(self):
        return "List the GIS GEORGIA plugin catalog"

    def tags(self):
        return ["catalog", "list", "plugins", "gis georgia"]

    def shortHelpString(self):
        return ("A table of the signed catalog: id, name, catalog version, installed version and "
                "state (installed / update / not_installed / incompatible / self).")

    def createInstance(self):
        return ListCatalogAlgorithm()

    def initAlgorithm(self, config=None):
        self._add_refresh()
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT, "Catalog"))

    def processAlgorithm(self, parameters, context, feedback):
        plugins = load_catalog(self.parameterAsBoolean(parameters, self.REFRESH, context), feedback)
        fields = QgsFields()
        for name in ("id", "name", "version", "installed", "state", "category", "algorithms"):
            fields.append(QgsField(name, QMetaType.Type.QString if name != "algorithms"
                                   else QMetaType.Type.Int))
        sink, dest = self.parameterAsSink(parameters, self.OUTPUT, context, fields,
                                          QgsWkbTypes.NoGeometry)
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        for p in plugins:
            have = installer_core.installed_version(p["id"])
            f = QgsFeature(fields)
            f.setAttributes([p["id"], p["name"], p["version"], have or "",
                             catalog.plugin_state(p, have, _qgis_version()), p.get("category", ""),
                             len((p.get("processing") or {}).get("algorithms", []))])
            sink.addFeature(f)
        return {self.OUTPUT: dest}
