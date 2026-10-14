# -*- coding: utf-8 -*-
"""Install / update / uninstall QGIS plugins from a verified ZIP.

Built on the public ``qgis.utils`` plugin functions (the same ones QGIS's own installer
uses) instead of ``pyplugin_installer``, whose ``installFromZipFile`` opens modal dialogs,
needs ``iface`` and differs between QGIS 3.44 and 4.x. Everything here can run (and be
tested) without a dialog.

Safety: HTTPS + host allow-list for downloads, SHA-256 check, a zip that must hold exactly
one plugin folder (no absolute paths, no ``..``), and a rollback of the previous version if
the new one cannot be put in place.
"""
from __future__ import annotations

import configparser
import hashlib
import io
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

ALLOWED_HOSTS = ("plugins.qgis.ge",)


class InstallError(Exception):
    """Any reason a plugin could not be installed; the message is user-presentable."""


@dataclass
class InstallResult:
    plugin_id: str
    version: str
    previous_version: str | None
    started: bool


# --------------------------------------------------------------------------- #
# Paths / settings
# --------------------------------------------------------------------------- #

def plugins_dir() -> str:
    """The profile's python/plugins folder (where QGIS installs user plugins)."""
    from qgis.core import QgsApplication
    path = os.path.join(QgsApplication.qgisSettingsDirPath(), "python", "plugins")
    return os.path.normpath(path)


def _read_version(plugin_dir: str) -> str | None:
    meta = os.path.join(plugin_dir, "metadata.txt")
    if not os.path.isfile(meta):
        return None
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(meta, encoding="utf-8")
        return cp.get("general", "version").strip()
    except Exception:  # noqa: BLE001
        return None


def installed_version(plugin_id: str, base: str | None = None) -> str | None:
    """Version of the plugin installed in the profile, or None."""
    return _read_version(os.path.join(base or plugins_dir(), plugin_id))


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def check_url(url: str, allowed_hosts=ALLOWED_HOSTS) -> None:
    u = urlparse(url)
    if u.scheme != "https":
        raise InstallError("Only HTTPS downloads are allowed: {}".format(url))
    if (u.hostname or "").lower() not in allowed_hosts:
        raise InstallError("Download host is not allowed: {}".format(u.hostname))


def download(url: str, allowed_hosts=ALLOWED_HOSTS) -> bytes:
    """Fetch ``url`` with QGIS's network stack (proxy / auth aware). Blocking."""
    check_url(url, allowed_hosts)
    from qgis.core import QgsBlockingNetworkRequest
    from qgis.PyQt.QtCore import QUrl
    from qgis.PyQt.QtNetwork import QNetworkRequest

    req = QNetworkRequest(QUrl(url))
    blocking = QgsBlockingNetworkRequest()
    err = blocking.get(req, forceRefresh=True)
    if err != QgsBlockingNetworkRequest.NoError:
        raise InstallError("Download failed: {}".format(blocking.errorMessage()))
    return bytes(blocking.reply().content())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# ZIP validation
# --------------------------------------------------------------------------- #

def inspect_zip(data: bytes, expected_id: str | None = None) -> tuple[str, str]:
    """(plugin_id, version) of a plugin ZIP, or InstallError.

    The archive must contain exactly one top-level folder with a metadata.txt in it, and
    no entry may be absolute, contain ``..`` or a drive letter."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise InstallError("The downloaded file is not a valid ZIP.")
    names = zf.namelist()
    if not names:
        raise InstallError("The ZIP is empty.")
    roots = set()
    for n in names:
        norm = n.replace("\\", "/")
        parts = norm.split("/")
        if norm.startswith("/") or ".." in parts or (len(parts[0]) == 2 and parts[0][1] == ":"):
            raise InstallError("Unsafe path in ZIP: {}".format(n))
        roots.add(parts[0])
    if len(roots) != 1:
        raise InstallError("The ZIP must contain exactly one plugin folder.")
    plugin_id = roots.pop()
    if expected_id and plugin_id != expected_id:
        raise InstallError("Unexpected plugin folder '{}' (expected '{}').".format(
            plugin_id, expected_id))
    meta_name = plugin_id + "/metadata.txt"
    if meta_name not in names:
        raise InstallError("metadata.txt is missing in the plugin folder.")
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.read_string(zf.read(meta_name).decode("utf-8", "replace"))
    try:
        version = cp.get("general", "version").strip()
    except Exception:  # noqa: BLE001
        raise InstallError("metadata.txt has no version.")
    return plugin_id, version


def _extract(data: bytes, dest: str) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            target = os.path.normpath(os.path.join(dest, info.filename))
            if not target.startswith(os.path.normpath(dest) + os.sep) and target != os.path.normpath(dest):
                raise InstallError("Unsafe path in ZIP: {}".format(info.filename))
        zf.extractall(dest)


def _rmtree(path: str) -> None:
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


# --------------------------------------------------------------------------- #
# Install / uninstall
# --------------------------------------------------------------------------- #

def install_zip(data: bytes, expected_id: str | None = None,
                expected_sha256: str | None = None, base: str | None = None,
                activate: bool = True) -> InstallResult:
    """Install or update a plugin from ZIP bytes into the profile's plugin folder."""
    from qgis import utils

    if expected_sha256 and sha256_hex(data).lower() != expected_sha256.lower():
        raise InstallError("Checksum mismatch: the file is damaged or was changed.")
    plugin_id, version = inspect_zip(data, expected_id)

    base = base or plugins_dir()
    os.makedirs(base, exist_ok=True)
    target = os.path.join(base, plugin_id)
    previous = installed_version(plugin_id, base)

    staging = tempfile.mkdtemp(prefix="gg_hub_")
    backup = None
    was_loaded = utils.isPluginLoaded(plugin_id)
    try:
        _extract(data, staging)
        if was_loaded:
            utils.unloadPlugin(plugin_id)
        if os.path.exists(target) or os.path.islink(target):
            backup = target + ".gg_bak"
            if os.path.exists(backup):
                _rmtree(backup)
            os.replace(target, backup)
        try:
            shutil.copytree(os.path.join(staging, plugin_id), target, copy_function=shutil.copy)
        except Exception as exc:  # noqa: BLE001
            if os.path.exists(target):
                _rmtree(target)
            if backup:
                os.replace(backup, target)
                backup = None
            if was_loaded:
                _reload(plugin_id)
            raise InstallError("Could not store the plugin: {}".format(exc))
    finally:
        _rmtree(staging)
    if backup and os.path.exists(backup):
        _rmtree(backup)

    started = False
    if activate:
        started = _reload(plugin_id, force_enable=not was_loaded and previous is None)
    _refresh_plugin_manager()
    return InstallResult(plugin_id, version, previous, started)


def _reload(plugin_id: str, force_enable: bool = False) -> bool:
    """Re-scan, import and (when enabled) start the plugin. True if it is running."""
    from qgis import utils
    from qgis.core import QgsSettings

    utils.updateAvailablePlugins()
    if not utils.loadPlugin(plugin_id):
        return False
    settings = QgsSettings()
    key = "/PythonPlugins/" + plugin_id
    if settings.contains(key):
        if settings.value(key, False, bool):
            return bool(utils.startPlugin(plugin_id))
        return False
    ok = bool(utils.startPlugin(plugin_id))
    if ok:
        settings.setValue(key, True)
    return ok


def uninstall(plugin_id: str, base: str | None = None) -> bool:
    """Unload and delete an installed plugin. False if it was not installed."""
    from qgis import utils
    from qgis.core import QgsSettings

    base = base or plugins_dir()
    target = os.path.join(base, plugin_id)
    if not os.path.isdir(target):
        return False
    if utils.isPluginLoaded(plugin_id):
        utils.unloadPlugin(plugin_id)
    _rmtree(target)
    QgsSettings().remove("/PythonPlugins/" + plugin_id)
    utils.updateAvailablePlugins()
    _refresh_plugin_manager()
    return True


def _refresh_plugin_manager() -> None:
    """Best effort: let QGIS's Plugin Manager re-read the installed plugins."""
    try:
        import pyplugin_installer
        inst = pyplugin_installer.instance()
        if inst is not None:
            from pyplugin_installer.installer_data import plugins
            plugins.getAllInstalled()
            plugins.rebuild()
            inst.exportPluginsToManager()
    except Exception:  # noqa: BLE001
        pass
