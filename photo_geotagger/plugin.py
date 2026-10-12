from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from . import i18n

MENU = "Photo Geotagger"


class PhotoGeotaggerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(QgsApplication.getThemeIcon("/mActionAddImage.svg"),
                              i18n.t("title"), self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self):
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(MENU, self.action)
            self.action = None
        if self.dialog:
            self.dialog.deleteLater()
            self.dialog = None

    def run(self):
        from .dialog import GeotagDialog
        if self.dialog is None:
            self.dialog = GeotagDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
