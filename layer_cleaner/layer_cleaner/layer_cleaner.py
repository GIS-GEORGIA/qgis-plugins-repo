# -*- coding: utf-8 -*-
"""
================================================================================
Layer Cleaner - Main Plugin Class
================================================================================
"""

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsApplication, QgsProject

from . import cleaner_core


class LayerCleanerPlugin:
    """Main plugin class."""

    def __init__(self, iface):
        """Constructor.
        
        Args:
            iface: QGIS interface object
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.toolbar = None
        self.actions = []
        
        # Base layer names to keep
        self.keep_names = list(cleaner_core.KEEP_NAMES)
        self.provider = None

    def initProcessing(self):
        """Register the Processing provider (also called headless by qgis_process)."""
        if self.provider is not None:
            return
        from .processing_provider import LayerCleanerProvider
        self.provider = LayerCleanerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        """Initialize the plugin GUI."""
        self.initProcessing()
        # Create toolbar
        self.toolbar = self.iface.addToolBar("Layer Cleaner")
        self.toolbar.setObjectName("LayerCleanerToolbar")
        
        # Clean layers button
        icon_clean = QIcon(os.path.join(self.plugin_dir, "icons", "clean.png"))
        self.action_clean = QAction(icon_clean, "Clean Layers", self.iface.mainWindow())
        self.action_clean.setStatusTip("Remove all layers except base layers")
        self.action_clean.triggered.connect(self.clean_layers)
        self.toolbar.addAction(self.action_clean)
        self.actions.append(self.action_clean)
        
        # Add base layers button
        icon_add = QIcon(os.path.join(self.plugin_dir, "icons", "add.png"))
        self.action_add = QAction(icon_add, "Add Base Layers", self.iface.mainWindow())
        self.action_add.setStatusTip("Add Google Satellite and OpenStreetMap layers")
        self.action_add.triggered.connect(self.add_base_layers)
        self.toolbar.addAction(self.action_add)
        self.actions.append(self.action_add)
        
        # Add to Plugins menu
        self.iface.addPluginToMenu("Layer Cleaner", self.action_clean)
        self.iface.addPluginToMenu("Layer Cleaner", self.action_add)

    def unload(self):
        """Unload the plugin."""
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        # Remove menu items
        for action in self.actions:
            self.iface.removePluginMenu("Layer Cleaner", action)
        
        # Remove toolbar
        if self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            del self.toolbar

    def clean_layers(self):
        """Remove all layers except base layers."""
        project = QgsProject.instance()
        layers_to_remove = cleaner_core.layers_to_remove(project, self.keep_names)
        
        if not layers_to_remove:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Layer Cleaner",
                "No layers to remove!"
            )
            return
        
        # Confirm removal
        reply = QMessageBox.question(
            self.iface.mainWindow(),
            "Layer Cleaner",
            f"Remove {len(layers_to_remove)} layer(s)?\n\n"
            f"Base layers will be kept:\n- " + "\n- ".join(self.keep_names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for layer_id in layers_to_remove:
                project.removeMapLayer(layer_id)
            
            QMessageBox.information(
                self.iface.mainWindow(),
                "Layer Cleaner",
                f"Removed {len(layers_to_remove)} layer(s)!"
            )

    def add_base_layers(self):
        """Add Google Satellite Hybrid and OpenStreetMap layers."""
        added = cleaner_core.add_base_layers()
        
        # Show result
        if added:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Layer Cleaner",
                f"Added layers:\n- " + "\n- ".join(added)
            )
        else:
            QMessageBox.information(
                self.iface.mainWindow(),
                "Layer Cleaner",
                "Base layers already exist!"
            )
