# -*- coding: utf-8 -*-
"""Plugin bootstrap. Adds two actions under the Web menu/toolbar:

  * Georgian Cadastre…   -> NAPR code→parcel fetcher (CadastreDialog)
  * Cadastral Drawing…   -> survey drawing toolkit (CadastralDialog):
                            CRS 37/38 templates, WMS/WMTS services, name-based
                            styles, fonts, A4 layout, Excel attachment and
                            packaged export.
"""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .cadastre_dialog import CadastreDialog, _detect_lang
from . import i18n

# Menu/action label follows the QGIS UI locale; the dialog itself can still be
# switched on the fly. Show both names so it is findable either way.
MENU = u"{} / {}".format(
    i18n.t("window_title", "ka"), i18n.t("window_title", "en")
) if _detect_lang() == "ka" else i18n.t("window_title", "en")

# Second action label (drawing toolkit) — bilingual, locale-aware.
DRAW_LABEL = (u"საკადასტრო ნახაზი / Cadastral Drawing"
              if _detect_lang() == "ka" else u"Cadastral Drawing")


class GeorgianCadastrePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.draw_action = None
        self.dlg = None
        self.draw_dlg = None
        self._dir = os.path.dirname(__file__)

    def initGui(self):  # noqa: N802 (QGIS-required name)
        icon_path = os.path.join(self._dir, "icon.svg")
        self.action = QAction(
            QIcon(icon_path), MENU + u"…", self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToWebMenu(MENU, self.action)
        self.iface.addWebToolBarIcon(self.action)

        draw_icon = os.path.join(self._dir, "drawing", "resources", "icon.png")
        self.draw_action = QAction(
            QIcon(draw_icon), DRAW_LABEL + u"…", self.iface.mainWindow()
        )
        self.draw_action.triggered.connect(self.run_drawing)
        self.iface.addPluginToWebMenu(MENU, self.draw_action)
        self.iface.addWebToolBarIcon(self.draw_action)

    def unload(self):
        for act in (self.action, self.draw_action):
            if act is not None:
                self.iface.removePluginWebMenu(MENU, act)
                self.iface.removeWebToolBarIcon(act)
        self.action = None
        self.draw_action = None
        for dlg in (self.dlg, self.draw_dlg):
            if dlg is not None:
                dlg.close()
        self.dlg = None
        self.draw_dlg = None

    def run(self):
        # Reuse a single dialog instance so the last search stays available.
        if self.dlg is None:
            self.dlg = CadastreDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def run_drawing(self):
        if self.draw_dlg is None:
            from .drawing.dialog import CadastralDialog
            self.draw_dlg = CadastralDialog(self.iface, self.iface.mainWindow())
        self.draw_dlg.show()
        self.draw_dlg.raise_()
        self.draw_dlg.activateWindow()
