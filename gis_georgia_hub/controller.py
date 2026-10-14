# -*- coding: utf-8 -*-
"""Hub controller: loads the catalog, installs / removes plugins, checks for updates.

Network work runs in QgsTasks (background, cancellable); everything that touches the
plugin system (load / start / unload) runs back on the main thread.
"""
from __future__ import annotations

import os
import time

from qgis import utils
from qgis.core import Qgis, QgsApplication, QgsSettings, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal

from . import catalog, installer_core

CATALOG_URL = "https://plugins.qgis.ge/catalog.json"
REPO_NAME = "GIS GEORGIA"
REPO_URL = "https://plugins.qgis.ge/plugins.xml"
S = "gis_georgia_hub/"  # QgsSettings prefix


class _FuncTask(QgsTask):
    """Run ``fn()`` on a worker thread; ``done(result, error)`` runs on the main thread."""

    def __init__(self, description, fn, done):
        super().__init__(description, QgsTask.CanCancel)
        self._fn = fn
        self._done = done
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self._fn()
            return True
        except Exception as exc:  # noqa: BLE001 - reported to the GUI thread
            self.error = exc
            return False

    def finished(self, ok):
        self._done(self.result if ok else None, None if ok else (self.error or RuntimeError("cancelled")))


class HubController(QObject):
    catalogChanged = pyqtSignal()
    busyChanged = pyqtSignal(bool)
    message = pyqtSignal(str, int)  # text, Qgis.MessageLevel as int
    catalogError = pyqtSignal(str, bool)  # error text, True when an older copy is shown

    def __init__(self, parent=None, fetch=None, catalog_url=None, cache_path=None):
        super().__init__(parent)
        self._fetch = fetch or installer_core.download
        self.catalog_url = (catalog_url or QgsSettings().value(S + "catalog_url", "", str)
                            or CATALOG_URL)
        self.cache_path = cache_path or os.path.join(
            QgsApplication.qgisSettingsDirPath(), "gis_georgia_hub", "catalog.json")
        self.catalog = catalog.load_cache(self.cache_path)
        self._tasks = []
        self._busy = 0

    # ---- state ------------------------------------------------------------
    @property
    def plugins(self) -> list:
        return (self.catalog or {}).get("plugins", [])

    def qgis_version(self) -> str:
        return Qgis.version().split("-")[0]

    def installed_versions(self) -> dict:
        return {p["id"]: v for p in self.plugins
                if (v := installer_core.installed_version(p["id"]))}

    def is_enabled(self, plugin_id: str) -> bool:
        return utils.isPluginLoaded(plugin_id)

    def state(self, entry: dict) -> str:
        return catalog.plugin_state(entry, installer_core.installed_version(entry["id"]),
                                    self.qgis_version())

    def pending_updates(self) -> list:
        return catalog.updates(self.plugins, self.installed_versions(), self.qgis_version())

    # ---- tasks ------------------------------------------------------------
    def _run(self, description, fn, done):
        def finish(result, error):
            self._busy -= 1
            if self._busy == 0:
                self.busyChanged.emit(False)
            if task in self._tasks:
                self._tasks.remove(task)
            done(result, error)

        task = _FuncTask(description, fn, finish)
        self._tasks.append(task)
        self._busy += 1
        if self._busy == 1:
            self.busyChanged.emit(True)
        QgsApplication.taskManager().addTask(task)
        return task

    def is_busy(self) -> bool:
        return self._busy > 0

    # ---- catalog ----------------------------------------------------------
    def refresh(self, done=None):
        def work():
            return self._fetch(self.catalog_url).decode("utf-8")

        def finished(text, error):
            if error is None:
                try:
                    doc = catalog.parse_catalog(text)
                except catalog.CatalogError as exc:
                    error = exc
                else:
                    catalog.save_cache(self.cache_path, text)
                    self.catalog = doc
                    QgsSettings().setValue(S + "last_catalog", int(time.time()))
                    self.catalogChanged.emit()
            if error is not None:
                self.catalogError.emit(str(error), self.catalog is not None)
            if done:
                done(error is None)

        self._run("GIS Georgia Hub: catalog", work, finished)

    # ---- install / update -------------------------------------------------
    def install(self, entry: dict, done=None):
        """Download (thread) -> verify -> install and start (main thread)."""
        url = entry["download"]["url"]
        sha = entry["download"]["sha256"]
        old = installer_core.installed_version(entry["id"])

        def work():
            data = self._fetch(url)
            if installer_core.sha256_hex(data).lower() != sha.lower():
                raise installer_core.InstallError(
                    "Checksum mismatch: the file is damaged or was changed.")
            return data

        def finished(data, error):
            ok = False
            try:
                if error is not None:
                    raise error
                res = installer_core.install_zip(data, expected_id=entry["id"], expected_sha256=sha)
                ok = True
                if not res.started:
                    self.message.emit(self.tr_("not_started", name=entry["name"]), int(Qgis.MessageLevel.Warning))
                elif old:
                    self.message.emit(self.tr_("done_updated", name=entry["name"], old=old,
                                               version=res.version), int(Qgis.MessageLevel.Success))
                else:
                    self.message.emit(self.tr_("done_installed", name=entry["name"],
                                               version=res.version), int(Qgis.MessageLevel.Success))
            except Exception as exc:  # noqa: BLE001
                self.message.emit(self.tr_("failed", err=str(exc)), int(Qgis.MessageLevel.Critical))
            self.catalogChanged.emit()
            if done:
                done(ok)

        self._run("GIS Georgia Hub: {}".format(entry["name"]), work, finished)

    def uninstall(self, entry: dict) -> bool:
        try:
            ok = installer_core.uninstall(entry["id"])
        except Exception as exc:  # noqa: BLE001
            self.message.emit(self.tr_("failed", err=str(exc)), int(Qgis.MessageLevel.Critical))
            return False
        if ok:
            self.message.emit(self.tr_("done_removed", name=entry["name"]), int(Qgis.MessageLevel.Success))
        self.catalogChanged.emit()
        return ok

    def set_enabled(self, entry: dict, enabled: bool) -> None:
        pid = entry["id"]
        settings = QgsSettings()
        if enabled:
            utils.updateAvailablePlugins()
            if utils.loadPlugin(pid) and utils.startPlugin(pid):
                settings.setValue("/PythonPlugins/" + pid, True)
        else:
            if utils.isPluginLoaded(pid):
                utils.unloadPlugin(pid)
            settings.setValue("/PythonPlugins/" + pid, False)
        self.catalogChanged.emit()

    # ---- messages ---------------------------------------------------------
    lang = "en"

    def tr_(self, key, **kw):
        from . import i18n
        return i18n.t(key, self.lang, **kw)


# --------------------------------------------------------------------------- repository

def repository_registered(settings=None) -> bool:
    settings = settings or QgsSettings()
    settings.beginGroup("app/plugin_repositories")
    try:
        return any(settings.value(k + "/url", "", str).rstrip("/") == REPO_URL
                   for k in settings.childGroups())
    finally:
        settings.endGroup()


def register_repository(settings=None) -> bool:
    """Add our plugins.xml to QGIS's plugin repositories (same keys the Plugin Manager
    writes). True when added, False when it was already there."""
    settings = settings or QgsSettings()
    if repository_registered(settings):
        return False
    base = "app/plugin_repositories/" + REPO_NAME
    settings.setValue(base + "/url", REPO_URL)
    settings.setValue(base + "/enabled", True)
    settings.setValue(base + "/valid", True)
    try:  # let an already-open Plugin Manager notice it
        import pyplugin_installer
        from pyplugin_installer.installer_data import repositories
        repositories.load()
        inst = pyplugin_installer.instance()
        if inst is not None:
            inst.exportPluginsToManager()
    except Exception:  # noqa: BLE001
        pass
    return True
