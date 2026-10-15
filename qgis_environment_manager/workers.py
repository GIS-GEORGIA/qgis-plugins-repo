# -*- coding: utf-8 -*-
"""Background threads: finding installations (slow subprocess calls) and running install steps."""
from __future__ import annotations

from qgis.PyQt.QtCore import QThread, pyqtSignal

from .qgis_installer import instances, runner, system, uninstall


class InstallsWorker(QThread):
    """find_installs() runs dpkg-query / flatpak / rpm...: keep it off the GUI thread."""
    done = pyqtSignal(list)

    def run(self):
        try:
            self.done.emit(uninstall.find_installs(system.detect()))
        except Exception:  # noqa: BLE001 - diagnostics must never break the dialog
            self.done.emit([])


class StepsWorker(QThread):
    """Run install steps; output lines stream to ``line``; ``done`` carries (returncode, failed step)."""
    line = pyqtSignal(str)
    done = pyqtSignal(int, object)

    def __init__(self, steps, elevate, parent=None, run_steps=None):
        super().__init__(parent)
        self._steps = steps
        self._elevate = elevate
        self._run = run_steps or runner.run_steps

    def run(self):
        rc, failed = self._run(self._steps, on_line=lambda s: self.line.emit(s.rstrip("\n")), elevate=self._elevate)
        self.done.emit(rc, failed)


class UpdatesWorker(QThread):
    """check_updates() asks apt / flatpak / dnf...: some of it goes over the network, so keep it off the GUI thread."""
    done = pyqtSignal(list)

    def __init__(self, items, parent=None, check=None):
        super().__init__(parent)
        self._items = items
        self._check = check or instances.check_updates

    def run(self):
        try:
            self.done.emit(self._check(self._items))
        except Exception:  # noqa: BLE001 - a failed check must not break the window: it just reports nothing
            self.done.emit([])
