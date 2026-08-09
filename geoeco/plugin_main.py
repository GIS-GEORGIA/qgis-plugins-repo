"""
GeoEco plugin — თხელი ფენა. მთელ მუშაობას Processing provider აკეთებს,
ლოგიკას კი solar_wind_core (QGIS-ისგან დამოუკიდებელი). აქ მხოლოდ wiring-ია.
"""
from __future__ import annotations

import os
import sys

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QLocale

# solar_wind_core-ის მოძებნა ორ სცენარში:
#  1) გამოქვეყნებული zip — core ბანდლდება პლაგინის საქაღალდეშივე (_PLUGIN_DIR)
#  2) dev repo — core ერთი დონით ზემოთაა (_ROOT)
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PLUGIN_DIR)
for _p in (_PLUGIN_DIR, _ROOT):
    if os.path.isdir(os.path.join(_p, "solar_wind_core")) and _p not in sys.path:
        # append, not insert(0): geoeco/processing/ must not shadow
        # QGIS's built-in Processing plugin (import processing).
        sys.path.append(_p)

from .processing.provider import GeoEcoProvider  # noqa: E402


class GeoEcoPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self._install_translator()

    def _install_translator(self):
        """ka/en — Qt .qm თარგმანი (i18n/geoeco_ka.qm)."""
        locale = QLocale.system().name()  # მაგ. 'ka_GE'
        qm = os.path.join(_ROOT, "i18n", f"geoeco_{locale[:2]}.qm")
        if os.path.exists(qm):
            self.translator = QTranslator()
            self.translator.load(qm)
            QCoreApplication.installTranslator(self.translator)

    def initProcessing(self):
        self.provider = GeoEcoProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
