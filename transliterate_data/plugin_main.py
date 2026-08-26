# -*- coding: utf-8 -*-
"""
Transliterate Data — ქართული სახელების ლათინურ ტრანსლიტერაციაზე მასობრივი
გადარქმევა: shapefile ფაილები, ბაზების (gpkg/sqlite/gdb) ფაილები და მათ
შიგნით შრეები/feature class-ები და ველები. ეროვნული სუფთა სქემა; სხვა
სიმბოლოები → '_'. Preview→Apply ან ასლზე მუშაობა. ორენოვანი ka/en. GPLv3.
"""
from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from . import i18n

_DIR = os.path.dirname(os.path.abspath(__file__))


class TransliterateDataPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.lang = i18n.DEFAULT_LANG
        self.action = None

    def initGui(self):
        self.lang = i18n.DEFAULT_LANG   # ინგლისური default; ენა დიალოგში იცვლება
        icon = QIcon(os.path.join(_DIR, "icon.svg"))
        self.action = QAction(icon, i18n.t("title", self.lang), self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(i18n.t("menu", self.lang), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu(i18n.t("menu", self.lang), self.action)
            self.iface.removeToolBarIcon(self.action)
        self.action = None

    def run(self):
        from .dialog import TransliterateDialog
        dlg = TransliterateDialog(self.iface, self.iface.mainWindow())
        dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
