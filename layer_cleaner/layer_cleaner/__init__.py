# -*- coding: utf-8 -*-
"""
================================================================================
Layer Cleaner - QGIS Plugin
================================================================================

Description:
    This plugin allows you to clean layers from your project
    and add base layers (Google Satellite Hybrid, OpenStreetMap).

Features:
    - Remove all layers except base layers
    - Add Google Satellite Hybrid layer
    - Add OpenStreetMap layer

Author: Giorgi Kapanadze
Date: 2025
================================================================================
"""


def classFactory(iface):
    """Load the plugin."""
    from .layer_cleaner import LayerCleanerPlugin
    return LayerCleanerPlugin(iface)
