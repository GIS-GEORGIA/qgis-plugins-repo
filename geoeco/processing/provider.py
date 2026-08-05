"""GeoEco Processing provider — ერთი ქოლგა ყველა მოდულის ხელსაწყოსთვის."""
from __future__ import annotations

from qgis.core import QgsProcessingProvider

from .alg_solar_economics import SolarEconomicsAlgorithm
from .alg_wind_resource import WindResourceAlgorithm
from .alg_wind_raster import WindRasterAlgorithm


class GeoEcoProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(SolarEconomicsAlgorithm())
        self.addAlgorithm(WindResourceAlgorithm())
        self.addAlgorithm(WindRasterAlgorithm())
        # next: WindNinja terrain field, Tilt optimizer, Kriging + error map

    def id(self):
        return "geoeco"

    def name(self):
        return "GeoEco"

    def longName(self):
        return "GeoEco — Solar & Wind (last-mile)"
