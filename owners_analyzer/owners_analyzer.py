# -*- coding: utf-8 -*-
"""
================================================================================
მფლობელების ანალიზატორი - მთავარი კლასი
================================================================================
"""

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject

from .dialog import OwnersAnalyzerDialog


class OwnersAnalyzerPlugin:
    """მთავარი პლაგინის კლასი."""

    def __init__(self, iface):
        """კონსტრუქტორი.
        
        Args:
            iface: QGIS ინტერფეისის ობიექტი
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'მფლობელების ანალიზატორი'
        self.toolbar = self.iface.addToolBar('მფლობელების ანალიზატორი')
        self.toolbar.setObjectName('OwnersAnalyzerToolbar')
        self.dialog = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """ქმედების დამატება."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """პლაგინის ინტერფეისის ინიციალიზაცია."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        
        self.add_action(
            icon_path,
            text='მფლობელების ანალიზატორი',
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip='მფლობელების ანალიზი და სტატისტიკა'
        )

    def unload(self):
        """პლაგინის გამორთვა."""
        for action in self.actions:
            self.iface.removePluginMenu('მფლობელების ანალიზატორი', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """პლაგინის გაშვება."""
        # შემოწმება არის თუ არა შრეები
        layers = QgsProject.instance().mapLayers().values()
        vector_layers = [l for l in layers if l.type() == 0]  # 0 = VectorLayer
        
        if not vector_layers:
            QMessageBox.warning(
                self.iface.mainWindow(),
                'გაფრთხილება',
                'პროექტში ვექტორული შრეები არ მოიძებნა!'
            )
            return

        # დიალოგის შექმნა და გახსნა
        self.dialog = OwnersAnalyzerDialog(self.iface)
        self.dialog.show()
