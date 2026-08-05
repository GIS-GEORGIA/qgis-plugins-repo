# -*- coding: utf-8 -*-
"""Load WMS/WMTS/XYZ services from resources/services.json and add them to the
project. QGIS owns all the networking — we only assemble the data-source URI.
"""

import json
import os

from qgis.PyQt.QtCore import QUrl
from qgis.core import QgsRasterLayer, QgsProject

from . import config
from . import i18n

SERVICES_FILE = os.path.join(config.RESOURCES_DIR, "services.json")


def load_services():
    """Return the list of service dicts, or [] if the file is missing/invalid."""
    try:
        with open(SERVICES_FILE, encoding="utf-8") as fh:
            return json.load(fh).get("services", [])
    except (OSError, ValueError):
        return []


def service_label(svc):
    lang = i18n.current_language()
    return svc.get(f"name_{lang}") or svc.get("name_en") or svc.get("id", "?")


def is_ready(svc):
    """A service is usable when it has a non-empty url."""
    return bool(svc.get("url"))


def _enc(text):
    return QUrl.toPercentEncoding(text).data().decode()


def build_uri(svc):
    """Build the QGIS data-source URI + provider for a service dict.

    XYZ, WMS and WMTS all use the 'wms' provider. The remote URL is always
    percent-encoded so query strings (?service=…&request=…) don't break the
    URI parser.
    """
    stype = svc.get("type", "xyz").lower()
    url = svc.get("url", "")
    if stype == "xyz":
        params = ["type=xyz", f"url={_enc(url)}"]
        if "zmin" in svc:
            params.append(f"zmin={svc['zmin']}")
        if "zmax" in svc:
            params.append(f"zmax={svc['zmax']}")
        return "&".join(params), "wms"

    # WMS / WMTS
    parts = [
        "contextualWMSLegend=0",
        f"crs={svc.get('crs', 'EPSG:3857')}",
        "dpiMode=7",
        f"format={svc.get('format', 'image/png')}",
        f"layers={svc.get('layers', '')}",
        f"styles={svc.get('styles', '')}",
    ]
    if stype == "wmts":
        parts.append(f"tileMatrixSet={svc.get('tileMatrixSet', '')}")
    parts.append(f"url={_enc(url)}")
    return "&".join(parts), "wms"


def add_service(svc, project=None):
    """Add a service as a raster layer. Returns (layer, error_message)."""
    if not is_ready(svc):
        return None, "URL is empty — fill it in services.json first."
    project = project or QgsProject.instance()
    uri, provider = build_uri(svc)
    layer = QgsRasterLayer(uri, service_label(svc), provider)
    if not layer.isValid():
        return None, layer.error().summary() or "Invalid raster layer."
    project.addMapLayer(layer)
    # Push service basemaps to the bottom of the layer tree.
    root = project.layerTreeRoot()
    node = root.findLayer(layer.id())
    if node:
        clone = node.clone()
        root.addChildNode(clone)
        node.parent().removeChildNode(node)
    return layer, None
