# -*- coding: utf-8 -*-
"""
================================================================================
Layer Cleaner - Main Plugin Class
================================================================================
"""

import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject, QgsRasterLayer


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
        self.keep_names = ["Google Satellite Hybrid", "OpenStreetMap"]

    def initGui(self):
        """Initialize the plugin GUI."""
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
        layers_to_remove = []
        
        for layer in project.mapLayers().values():
            if layer.name() not in self.keep_names:
                layers_to_remove.append(layer.id())
        
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
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for layer_id in layers_to_remove:
                project.removeMapLayer(layer_id)
            
            QMessageBox.information(
                self.iface.mainWindow(),
                "Layer Cleaner",
                f"Removed {len(layers_to_remove)} layer(s)!"
            )

    def add_base_layers(self):
        """Add Google Satellite Hybrid and OpenStreetMap layers."""
        project = QgsProject.instance()
        added = []
        
        # Check if layer already exists
        def layer_exists(name):
            return any(lyr.name() == name for lyr in project.mapLayers().values())
        
        # Add Google Satellite Hybrid
        if not layer_exists("Google Satellite Hybrid"):
            url = "type=xyz&url=https://mt1.google.com/vt/lyrs=y%26x={x}%26y={y}%26z={z}"
            layer = QgsRasterLayer(url, "Google Satellite Hybrid", "wms")
            if layer.isValid():
                project.addMapLayer(layer)
                added.append("Google Satellite Hybrid")
        
        # Add OpenStreetMap
        if not layer_exists("OpenStreetMap"):
            url = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            layer = QgsRasterLayer(url, "OpenStreetMap", "wms")
            if layer.isValid():
                project.addMapLayer(layer)
                added.append("OpenStreetMap")
        
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
