"""
Solar Economics algorithm — არსებული რადიაციის რასტრიდან (SAGA/GRASS output)
→ გამომუშავების (kWh) და შემოსავლის (₾) რასტრი.

ესაა "ბოლო მილის" ტიპური მაგალითი: ფიზიკას არ ვითვლით — ვიღებთ მზა
რადიაციის რასტრს input-ად და ვამატებთ იმას, რაც ძრავას აკლია.
მთელი მათემატიკა solar_wind_core-შია (QGIS-ის გარეშე ტესტირებადი).
"""
from __future__ import annotations

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterNumber,
)
from qgis.PyQt.QtCore import QCoreApplication

from solar_wind_core.solar import pv_yield


class SolarEconomicsAlgorithm(QgsProcessingAlgorithm):
    IN_RAD = "RADIATION"
    KWP = "KWP"
    PR = "PR"
    TARIFF = "TARIFF"
    OUT_ENERGY = "OUT_ENERGY"
    OUT_REVENUE = "OUT_REVENUE"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.IN_RAD, self.tr("რადიაციის რასტრი (kWh/m²/yr)")))
        self.addParameter(QgsProcessingParameterNumber(
            self.KWP, self.tr("დადგმული სიმძლავრე (kWp per m²-ჩ. თუ 0 → area method)"),
            defaultValue=0.2, type=QgsProcessingParameterNumber.Double))
        self.addParameter(QgsProcessingParameterNumber(
            self.PR, self.tr("Performance Ratio"), defaultValue=0.75,
            type=QgsProcessingParameterNumber.Double))
        self.addParameter(QgsProcessingParameterNumber(
            self.TARIFF, self.tr("ტარიფი (₾/kWh)"), defaultValue=0.20,
            type=QgsProcessingParameterNumber.Double))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_ENERGY, self.tr("გამომუშავება (kWh)")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_REVENUE, self.tr("შემოსავალი (₾)")))

    def processAlgorithm(self, parameters, context, feedback):
        import numpy as np
        from solar_wind_core import raster_io

        rad_layer = self.parameterAsRasterLayer(parameters, self.IN_RAD, context)
        kwp = self.parameterAsDouble(parameters, self.KWP, context)
        pr = self.parameterAsDouble(parameters, self.PR, context)
        tariff = self.parameterAsDouble(parameters, self.TARIFF, context)
        out_e = self.parameterAsOutputLayer(parameters, self.OUT_ENERGY, context)
        out_r = self.parameterAsOutputLayer(parameters, self.OUT_REVENUE, context)

        rad = raster_io.read_raster(rad_layer.source())
        H = rad.array.astype("float64")

        # core ლოგიკა — QGIS-ის გარეშე ტესტირებადი ფუნქციები
        energy = pv_yield.energy_kwp_method(H, kwp, pr)
        revenue = energy * tariff

        if rad.nodata is not None:
            mask = rad.array == rad.nodata
            energy[mask] = rad.nodata
            revenue[mask] = rad.nodata

        raster_io.write_raster(out_e, raster_io.RasterData(
            energy.astype("float32"), rad.geotransform, rad.projection, rad.nodata))
        raster_io.write_raster(out_r, raster_io.RasterData(
            revenue.astype("float32"), rad.geotransform, rad.projection, rad.nodata))

        total = float(np.nansum(energy[energy != (rad.nodata or np.nan)]))
        feedback.pushInfo(self.tr(f"ჯამური გამომუშავება ≈ {total:,.0f} kWh/yr"))
        return {self.OUT_ENERGY: out_e, self.OUT_REVENUE: out_r}

    def tr(self, s):
        return QCoreApplication.translate("GeoEco", s)

    def name(self):
        return "solar_economics"

    def displayName(self):
        return self.tr("Solar: energy & revenue / მზე: ენერგია და შემოსავალი")

    def group(self):
        return self.tr("Energy / ენერგია")

    def groupId(self):
        return "energy"

    def createInstance(self):
        return SolarEconomicsAlgorithm()
