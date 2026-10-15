# -*- coding: utf-8 -*-
"""Plugin shell: one menu entry and toolbar button that open the window."""
from __future__ import annotations

import datetime
import os

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from . import diagnostics, strings
from .workers import FuncWorker

SETTINGS = "qgis_environment_manager/"
STARTUP_DELAY_MS = 25000                       # after QGIS has finished starting: this must never slow the start itself


def startup_enabled() -> bool:
    return QgsSettings().value(SETTINGS + "startup_check", False, bool)


class EnvManagerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None
        self._dir = os.path.dirname(os.path.abspath(__file__))
        self._startup_fn = None                # tests: () -> {"diagnostics": [...], "doctor": {...}}
        self._startup_worker = None
        self._timer = None

    def initGui(self):  # noqa: N802
        lang = strings.resolve_lang(QgsApplication.locale(),
                                    QgsSettings().value("qgis_environment_manager/lang", "", str))
        self.action = QAction(QIcon(os.path.join(self._dir, "icon.svg")), strings.t("title", lang),
                              self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&QGIS Environment Manager", self.action)
        self.iface.addToolBarIcon(self.action)
        if startup_enabled():                  # off unless the user turned it on
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.start_check)
            self._timer.start(STARTUP_DELAY_MS)

    def start_check(self) -> bool:
        """Once a day, if the user asked for it: look at this QGIS in the background and say something only when there is something to say."""
        if not startup_enabled():
            return False
        settings = QgsSettings()
        today = datetime.date.today().isoformat()
        if settings.value(SETTINGS + "last_check", "", str) == today:
            return False
        settings.setValue(SETTINGS + "last_check", today)       # first: a check that fails is not repeated all day
        facts = diagnostics.gather_facts() if self._startup_fn is None else {}
        fn = self._startup_fn or (lambda: _default_check(facts))
        self._startup_worker = FuncWorker(fn)
        self._startup_worker.done.connect(self._announce)
        self._startup_worker.start()
        return True

    def _announce(self, result):
        lang = strings.resolve_lang(QgsApplication.locale(), QgsSettings().value(SETTINGS + "lang", "", str))
        if isinstance(result, Exception) or not result:
            return                                              # a failed check is silent: it must never be a nuisance
        problems = [f for f in result["doctor"]["findings"] if f[0] == "problem"]
        warns = [f for f in result["doctor"]["findings"] if f[0] == "warn"] + [f for f in result["diagnostics"] if f[0] == "warn"]
        if not problems and not warns:
            return
        n = len(problems) + len(warns)
        text = strings.t("sn_text", lang, n=n, problems=len(problems))
        level = Qgis.MessageLevel.Critical if problems else Qgis.MessageLevel.Warning
        self.iface.messageBar().pushMessage(strings.t("title", lang), text, level, 15)

    def unload(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.action is not None:
            self.iface.removePluginMenu("&QGIS Environment Manager", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dlg is not None:
            self.dlg.close()
            self.dlg = None

    def run(self):
        from .dialog import EnvDialog
        if self.dlg is None:
            self.dlg = EnvDialog(self.iface, self.iface.mainWindow())
        else:
            self.dlg.refresh()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()


def _default_check(facts):
    """In the worker thread: the installations, the findings about this QGIS and the doctor's (all read-only)."""
    from .qgis_installer import doctor, system, uninstall
    info = system.detect()
    installs = uninstall.find_installs(info) if facts.get("is_linux") else []
    return {"diagnostics": diagnostics.analyze(facts, installs),
            "doctor": doctor.run_all(installs, info, python_gdal=facts.get("gdal") or None)}
