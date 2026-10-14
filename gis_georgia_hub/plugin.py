# -*- coding: utf-8 -*-
"""Plugin shell: menu entry, startup update notice, first-run repository question."""
from __future__ import annotations

import os
import time

from qgis.core import Qgis, QgsApplication, QgsSettings
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton

from . import catalog, i18n
from .controller import S, HubController, register_repository, repository_registered

UPDATE_CHECK_EVERY = 12 * 3600  # seconds


class GisGeorgiaHubPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None
        self.ctl = None
        self._dir = os.path.dirname(os.path.abspath(__file__))
        self._timer = None

    def _lang(self):
        return i18n.resolve_lang(QgsApplication.locale(), QgsSettings().value(S + "lang", "", str))

    def initGui(self):
        self.ctl = HubController()
        self.ctl.lang = self._lang()
        label = i18n.t("title", self.ctl.lang)
        self.action = QAction(QIcon(os.path.join(self._dir, "icon.svg")), label,
                              self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&GIS Georgia", self.action)
        self.iface.addToolBarIcon(self.action)
        # let QGIS finish starting before we touch the network or ask anything
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._startup)
        self._timer.start(6000)

    def unload(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.action is not None:
            self.iface.removePluginMenu("&GIS Georgia", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dlg is not None:
            self.dlg.close()
            self.dlg = None
        self.ctl = None

    def run(self):
        from .dialog import HubDialog
        if self.dlg is None:
            self.dlg = HubDialog(self.ctl, self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
        self.ctl.refresh()

    # ---- startup -----------------------------------------------------------
    def _startup(self):
        settings = QgsSettings()
        lang = self._lang()
        # one-time question; never asked again whatever the answer
        if not settings.value(S + "repo_asked", False, bool):
            settings.setValue(S + "repo_asked", True)
            if not repository_registered() and self._ask_repo(lang) and register_repository():
                self.iface.messageBar().pushMessage(
                    "GIS Georgia", i18n.t("repo_added", lang), Qgis.MessageLevel.Success, 6)
        if not settings.value(S + "check_updates", True, bool):
            return
        last = settings.value(S + "last_update_check", 0, int)
        if time.time() - last < UPDATE_CHECK_EVERY:
            return
        settings.setValue(S + "last_update_check", int(time.time()))
        self.ctl.refresh(done=self._after_startup_refresh)

    def _ask_repo(self, lang: str) -> bool:
        ans = QMessageBox.question(
            self.iface.mainWindow(), i18n.t("repo_title", lang), i18n.t("repo_text", lang))
        return ans == QMessageBox.StandardButton.Yes

    def _after_startup_refresh(self, ok: bool):
        if not ok or self.ctl is None:
            return
        pending = self.ctl.pending_updates()
        if not pending:
            return
        lang = self._lang()
        names = ", ".join(catalog.display_name(p, lang) for p in pending)
        bar = self.iface.messageBar()
        item = bar.createMessage("GIS Georgia", i18n.t("updates_msg", lang, names=names))
        button = QPushButton(i18n.t("open_hub", lang))
        button.clicked.connect(self.run)
        item.layout().addWidget(button)
        bar.pushWidget(item, Qgis.MessageLevel.Info, 0)
