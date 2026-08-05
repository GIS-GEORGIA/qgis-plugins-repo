"""GeoEco Processing provider — ერთი ქოლგა ყველა მოდულის ხელსაწყოსთვის."""
from __future__ import annotations

from qgis.core import QgsProcessingProvider

from .alg_solar_economics import SolarEconomicsAlgorithm
from .alg_wind_resource import WindResourceAlgorithm


class GeoEcoProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(SolarEconomicsAlgorithm())
        self.addAlgorithm(WindResourceAlgorithm())
        # v0.5+: TiltOptimizerAlgorithm, WindNinja field, IDW raster, ...

    def id(self):
        return "geoeco"

    def name(self):
        return "GeoEco"

    def longName(self):
        return "GeoEco — Solar & Wind (last-mile)"
