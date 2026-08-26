# -*- coding: utf-8 -*-
"""
plugin.py — QGIS ფლაგინის მთავარი კლასი.

ამატებს ღილაკს QGIS-ის ტულბარსა და მენიუში; დაჭერისას ხსნის დიალოგს
იმავე DownloaderWidget-ით, რომელსაც ცალკე პროგრამა იყენებს.
"""

try:
    from .qt import QAction, QDialog, QVBoxLayout
    from .gui import DownloaderWidget
except ImportError:
    from qt import QAction, QDialog, QVBoxLayout
    from gui import DownloaderWidget

MENU = "&Plugin Downloader"


class PluginDownloader:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction("ყველა ფლაგინის ჩამოტვირთვა…", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self):
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.dialog is None:
            self.dialog = QDialog(self.iface.mainWindow())
            self.dialog.setWindowTitle("QGIS Plugin Downloader")
            layout = QVBoxLayout(self.dialog)
            layout.addWidget(DownloaderWidget())
            self.dialog.resize(720, 560)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
