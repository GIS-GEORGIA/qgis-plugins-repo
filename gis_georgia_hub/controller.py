# -*- coding: utf-8 -*-
"""Hub controller: loads the catalog, installs / removes plugins, checks for updates.

Network work runs in QgsTasks (background, cancellable); everything that touches the
plugin system (load / start / unload) runs back on the main thread.
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlparse

from qgis import utils
from qgis.core import Qgis, QgsApplication, QgsSettings, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtGui import QIcon

from . import catalog, installer_core, signing

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
    iconsChanged = pyqtSignal()
    progress = pyqtSignal(str, int, int)  # plugin name, index, total

    def __init__(self, parent=None, fetch=None, catalog_url=None, cache_path=None, trusted_keys=None):
        super().__init__(parent)
        self._trusted = trusted_keys
        self._fetch = fetch or installer_core.download
        self.catalog_url = (catalog_url or QgsSettings().value(S + "catalog_url", "", str)
                            or CATALOG_URL)
        self.cache_path = cache_path or os.path.join(
            QgsApplication.qgisSettingsDirPath(), "gis_georgia_hub", "catalog.json")
        self.catalog = catalog.load_cache(self.cache_path, self._verify)
        self.icon_dir = os.path.join(os.path.dirname(self.cache_path), "icons")
        self._icons_pending = False
        self._tasks = []
        self._busy = 0

    def _verify(self, data: bytes, sig_text) -> None:
        signing.verify_catalog(data, sig_text, self._trusted)

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
            return catalog.fetch_verified(self._fetch, self.catalog_url, self._verify)

        def finished(result, error):
            if error is None:
                text, sig_text = result
                try:
                    doc = catalog.parse_catalog(text)
                except catalog.CatalogError as exc:
                    error = exc
                else:
                    catalog.save_cache(self.cache_path, text, sig_text)
                    self.catalog = doc
                    QgsSettings().setValue(S + "last_catalog", int(time.time()))
                    self.catalogChanged.emit()
                    self.fetch_icons()
            if error is not None:
                self.catalogError.emit(str(error), self.catalog is not None)
            if done:
                done(error is None)

        self._run("GIS Georgia Hub: catalog", work, finished)

    # ---- icons ------------------------------------------------------------
    def _icon_file(self, entry: dict):
        url = entry.get("icon_url")
        if not url:
            return None
        ext = os.path.splitext(urlparse(url).path)[1] or ".png"
        return os.path.join(self.icon_dir, "{}-{}{}".format(entry["id"], entry["version"], ext))

    def icon_for(self, entry: dict):
        """A QIcon from the cache, or None (the list then shows the emoji)."""
        path = self._icon_file(entry)
        if path and os.path.isfile(path):
            icon = QIcon(path)
            return icon if not icon.isNull() else None
        return None

    def fetch_icons(self):
        """Download the icons that are not cached yet (background, best effort)."""
        todo = [(p, self._icon_file(p)) for p in self.plugins
                if p.get("icon_url") and self._icon_file(p) and not os.path.isfile(self._icon_file(p))]
        if not todo or self._icons_pending:
            return

        def work():
            os.makedirs(self.icon_dir, exist_ok=True)
            got = 0
            for entry, path in todo:
                try:
                    data = self._fetch(entry["icon_url"])
                except Exception:  # noqa: BLE001 - an icon is never worth an error
                    continue
                if data[:5] == b"<html" or len(data) < 20:
                    continue
                with open(path, "wb") as fh:
                    fh.write(data)
                got += 1
            return got

        def finished(got, _error):
            self._icons_pending = False
            if got:
                self.iconsChanged.emit()

        self._icons_pending = True
        self._run("GIS Georgia Hub: icons", work, finished)

    # ---- update all -------------------------------------------------------
    def update_all(self, done=None):
        """Update every plugin that has a newer catalog version, one after the other."""
        queue = list(self.pending_updates())
        total = len(queue)
        results = []

        def step(_ok=None):
            if _ok is not None:
                results.append(_ok)
            if not queue:
                if done:
                    done(results)
                return
            entry = queue.pop(0)
            self.progress.emit(entry["name"], total - len(queue), total)
            self.install(entry, done=step)

        step()

    def hub_update(self):
        """The catalog entry of the Hub when a newer version than the installed one exists."""
        entry = next((p for p in self.plugins if p["id"] == catalog.SELF_ID), None)
        have = installer_core.installed_version(catalog.SELF_ID)
        if entry and have and catalog.compare_versions(entry["version"], have) > 0:
            return entry
        return None

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
