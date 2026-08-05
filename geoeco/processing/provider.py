"""GeoEco Processing provider — ერთი ქოლგა ყველა მოდულის ხელსაწყოსთვის."""
from __future__ import annotations

from qgis.core import QgsProcessingProvider

from .alg_solar_economics import SolarEconomicsAlgorithm


class GeoEcoProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(SolarEconomicsAlgorithm())
        # v0.4+: WindResourceAlgorithm, TiltOptimizerAlgorithm, ...

    def id(self):
        return "geoeco"

    def name(self):
        return "GeoEco"

    def longName(self):
        return "GeoEco — Solar & Wind (last-mile)"
