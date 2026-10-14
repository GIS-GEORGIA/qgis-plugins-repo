# -*- coding: utf-8 -*-
"""Plugin shell: one menu entry and toolbar button that open the window."""
from __future__ import annotations

import os

from qgis.core import QgsApplication, QgsSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from . import strings


class EnvManagerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None
        self._dir = os.path.dirname(os.path.abspath(__file__))

    def initGui(self):  # noqa: N802
        lang = strings.resolve_lang(QgsApplication.locale(),
                                    QgsSettings().value("qgis_environment_manager/lang", "", str))
        self.action = QAction(QIcon(os.path.join(self._dir, "icon.svg")), strings.t("title", lang),
                              self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&QGIS Environment Manager", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
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
