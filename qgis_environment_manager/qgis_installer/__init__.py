"""qgis_installer - the logic of the QGIS installer, without any UI toolkit.

Used by the Tk program (qgis-installer-gui.py), the command line (qgis-installer-cli) and,
later, the QGIS plugin. Everything here is plain Python 3 and importable on any OS; the
functions that look at the machine (detect, find_installs) return empty/neutral data off Linux.
"""
__version__ = "0.7.0"          # the same as pyproject.toml (a test keeps them equal)

from .i18n import STR, label_for, steps_text, t
from . import doctor, envspec, instances, pluginscan, recipes, requirements, simulate, update, versions  # noqa: F401
from .plan import build_install, sources_text, steps_script
from .runner import default_elevator, needs_elevation_fallback, run_steps, write_root_script
from .system import (CHANNELS, KEY_FPR, KEY_URL, KEYRING, LATEST, LTR, LTR_ONLY_CHANNELS, SOURCES,
                     SUFFIX, SUPPORT, allowed_channels, default_channel, detect, installed_qgis,
                     method_available, read_os_release)
from .uninstall import USER_DATA, build_remove_steps, default_selection, find_installs

__all__ = [
    "STR", "label_for", "steps_text", "t", "build_install", "sources_text", "steps_script",
    "default_elevator", "needs_elevation_fallback", "run_steps", "write_root_script",
    "CHANNELS", "KEY_FPR", "KEY_URL", "KEYRING", "LATEST", "LTR", "LTR_ONLY_CHANNELS", "SOURCES",
    "SUFFIX", "SUPPORT", "allowed_channels", "default_channel", "detect", "installed_qgis",
    "method_available", "read_os_release", "USER_DATA", "build_remove_steps", "default_selection",
    "find_installs", "requirements", "recipes", "update", "instances", "simulate", "versions", "envspec", "doctor", "pluginscan",
]
