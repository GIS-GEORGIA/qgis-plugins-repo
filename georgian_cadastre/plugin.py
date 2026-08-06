# -*- coding: utf-8 -*-
"""Plugin bootstrap. Adds ONE action under the Web menu/toolbar:

  * Georgian Cadastre…  -> central hub dialog (drawing.CadastralDialog).

The hub carries every tool as a tab: fetch parcel by code (maps.gov.ge / NAPR)
including a map-click reverse and a 'batch / export' button that opens the full
NAPR dialog; CRS 37/38 templates; WMS/WMTS services; name-based styles; fonts;
A4 layout; Excel attachment and packaged export.
"""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .cadastre_dialog import _detect_lang
from . import i18n

# Menu/action label follows the QGIS UI locale; the dialog can still be switched
# on the fly. Show both names so it is findable either way.
MENU = u"{} / {}".format(
    i18n.t("window_title", "ka"), i18n.t("window_title", "en")
) if _detect_lang() == "ka" else i18n.t("window_title", "en")


class GeorgianCadastrePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None
        self._dir = os.path.dirname(__file__)

    def initGui(self):  # noqa: N802 (QGIS-required name)
        icon_path = os.path.join(self._dir, "icon.svg")
        self.action = QAction(
            QIcon(icon_path), MENU + u"…", self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToWebMenu(MENU, self.action)
        self.iface.addWebToolBarIcon(self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removePluginWebMenu(MENU, self.action)
            self.iface.removeWebToolBarIcon(self.action)
            self.action = None
        if self.dlg is not None:
            self.dlg.close()
            self.dlg = None

    def run(self):
        # Reuse a single hub dialog instance so state persists between opens.
        if self.dlg is None:
            from .drawing.dialog import CadastralDialog
            self.dlg = CadastralDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
