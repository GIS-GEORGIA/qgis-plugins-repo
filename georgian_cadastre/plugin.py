# -*- coding: utf-8 -*-
"""Plugin bootstrap: adds a 'Georgian Cadastre…' action to the Web menu/toolbar."""
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
        # Reuse a single dialog instance so the last search stays available.
        if self.dlg is None:
            self.dlg = CadastreDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()
