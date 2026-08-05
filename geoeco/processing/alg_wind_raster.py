"""
Wind Resource RASTER algorithm (v0.5) — წერტილებიდან უწყვეტი ქარის რუკა.

წერტილოვანი სადგურები → IDW ინტერპოლაცია → hub-height სიჩქარის, power density-ისა
და წლიური ენერგიის (AEP) რასტrები.

მთელი მათემატიკა solar_wind_core-შია (numpy-ვექტორიზებული, QGIS-ის გარეშე ტესტ.):
  interpolation.idw_numpy · weibull.power_density_from_mean · power_curve.aep_lookup

შენიშვნა: IDW მანძილებს და პიქსელს მეტrებში ითვლის — გამომავალი CRS პროექცირებული
უნდა იყოს (მაგ. UTM / EPSG:32638 საქართველოსთვის). გეოგრაფიულ CRS-ზე warning-ს იძლევა.
რელიეფური აჩქარება (ქედები) IDW-ს არ ესმის — ეს WindNinja-ს საქმეა (მომდევნო ეტაპი).
"""
from __future__ import annotations

import math

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterExtent,
    QgsProcessingParameterCrs,
    QgsProcessingParameterRasterDestination,
    QgsProcessing,
    QgsCoordinateTransform,
    QgsProject,
)
from qgis.PyQt.QtCore import QCoreApplication

from solar_wind_core import raster_io
from solar_wind_core.wind import interpolation, weibull, power_curve


class WindRasterAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    SPEED_FIELD = "SPEED_FIELD"
    MEAS_H = "MEAS_H"
    HUB_H = "HUB_H"
    ALPHA = "ALPHA"
    K_FIXED = "K_FIXED"
    POWER = "POWER"
    PIXEL = "PIXEL"
    EXTENT = "EXTENT"
    CRS = "CRS"
    RATED = "RATED"
    CUT_IN = "CUT_IN"
    RATED_SPEED = "RATED_SPEED"
    CUT_OUT = "CUT_OUT"
    OUT_SPEED = "OUT_SPEED"
    OUT_PDENS = "OUT_PDENS"
    OUT_AEP = "OUT_AEP"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr("სადგურები (წერტილები)"),
            [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField(
            self.SPEED_FIELD, self.tr("საშ. ქარის სიჩქარის ველი [m/s]"),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self._num(self.MEAS_H, "გაზომვის სიმაღლე [m]", 10.0)
        self._num(self.HUB_H, "Hub height [m]", 80.0)
        self._num(self.ALPHA, "Wind shear exponent α", 0.14)
        self._num(self.K_FIXED, "Weibull k", 2.0)
        self._num(self.POWER, "IDW power", 2.0)
        self._num(self.PIXEL, "პიქსელის ზომა [m]", 100.0)
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT, self.tr("გამომავალი გაფართოება (extent)")))
        self.addParameter(QgsProcessingParameterCrs(
            self.CRS, self.tr("გამომავალი CRS (პროექცირებული!)"),
            defaultValue="EPSG:32638", optional=True))
        self._num(self.RATED, "ტურბინის rated power [kW]", 2000.0)
        self._num(self.CUT_IN, "Cut-in [m/s]", 3.0)
        self._num(self.RATED_SPEED, "Rated speed [m/s]", 12.0)
        self._num(self.CUT_OUT, "Cut-out [m/s]", 25.0)
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_SPEED, self.tr("სიჩქარე hub-ზე [m/s]")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_PDENS, self.tr("Power density [W/m²]")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_AEP, self.tr("AEP [MWh/yr]")))

    def _num(self, name, label, default):
        self.addParameter(QgsProcessingParameterNumber(
            name, self.tr(label), defaultValue=default,
            type=QgsProcessingParameterNumber.Double))

    def processAlgorithm(self, parameters, context, feedback):
        import numpy as np

        source = self.parameterAsSource(parameters, self.INPUT, context)
        speed_field = self.parameterAsString(parameters, self.SPEED_FIELD, context)
        meas_h = self.parameterAsDouble(parameters, self.MEAS_H, context)
        hub_h = self.parameterAsDouble(parameters, self.HUB_H, context)
        alpha = self.parameterAsDouble(parameters, self.ALPHA, context)
        k = self.parameterAsDouble(parameters, self.K_FIXED, context)
        power = self.parameterAsDouble(parameters, self.POWER, context)
        pixel = self.parameterAsDouble(parameters, self.PIXEL, context)
        rated = self.parameterAsDouble(parameters, self.RATED, context)
        cut_in = self.parameterAsDouble(parameters, self.CUT_IN, context)
        rated_sp = self.parameterAsDouble(parameters, self.RATED_SPEED, context)
        cut_out = self.parameterAsDouble(parameters, self.CUT_OUT, context)

        out_crs = self.parameterAsCrs(parameters, self.CRS, context)
        if not out_crs or not out_crs.isValid():
            out_crs = source.sourceCrs()
        if out_crs.isGeographic():
            feedback.pushWarning(self.tr(
                "⚠ CRS გეოგრაფიულია — მანძილი/პიქსელი გრადუსებში იქნება. "
                "სჯობს პროექცირებული CRS (მაგ. EPSG:32638)."))
        extent = self.parameterAsExtent(parameters, self.EXTENT, context, out_crs)
        if extent.isEmpty():
            raise ValueError(self.tr("ცარიელი extent"))

        # --- სადგურების შეგროვება out_crs-ში, hub-height კორექციით ---
        tr = QgsCoordinateTransform(source.sourceCrs(), out_crs, QgsProject.instance())
        xs, ys, vals = [], [], []
        for feat in source.getFeatures():
            v = feat[speed_field]
            geom = feat.geometry()
            if v is None or v <= 0 or geom is None or geom.isEmpty():
                continue
            pt = geom.centroid().asPoint()
            p = tr.transform(pt)
            xs.append(p.x())
            ys.append(p.y())
            vals.append(interpolation.height_correction(float(v), meas_h, hub_h, alpha))
        if len(xs) < 1:
            raise ValueError(self.tr("ვერცერთი ვალიდური სადგური ვერ მოიძებნა"))
        feedback.pushInfo(self.tr(f"სადგურები: {len(xs)}"))

        # --- გამომავალი ბადე ---
        xmin, ymin, xmax, ymax = extent.xMinimum(), extent.yMinimum(), \
            extent.xMaximum(), extent.yMaximum()
        cols = max(1, int(math.ceil((xmax - xmin) / pixel)))
        rows = max(1, int(math.ceil((ymax - ymin) / pixel)))
        col_c = xmin + (np.arange(cols) + 0.5) * pixel
        row_c = ymax - (np.arange(rows) + 0.5) * pixel
        XX, YY = np.meshgrid(col_c, row_c)

        # --- IDW → სიჩქარე, power density, AEP ---
        feedback.pushInfo(self.tr(f"ბადე: {cols}×{rows}, IDW…"))
        speed = interpolation.idw_numpy(np.array(xs), np.array(ys),
                                        np.array(vals), XX, YY, power)
        pdens = weibull.power_density_from_mean(speed, k)
        curve = power_curve.PowerCurve(rated, cut_in, rated_sp, cut_out)
        means, aeps = power_curve.aep_lookup(curve, k, v_mean_max=cut_out, step=0.25)
        aep_mwh = np.interp(speed, means, aeps) / 1000.0

        gt = (xmin, pixel, 0.0, ymax, 0.0, -pixel)
        wkt = out_crs.toWkt()
        out_speed = self.parameterAsOutputLayer(parameters, self.OUT_SPEED, context)
        out_pdens = self.parameterAsOutputLayer(parameters, self.OUT_PDENS, context)
        out_aep = self.parameterAsOutputLayer(parameters, self.OUT_AEP, context)
        for arr, path in ((speed, out_speed), (pdens, out_pdens), (aep_mwh, out_aep)):
            raster_io.write_raster(path, raster_io.RasterData(
                arr.astype("float32"), gt, wkt, nodata=None))

        feedback.pushInfo(self.tr(
            f"საშ. სიჩქარე {float(speed.mean()):.2f} m/s · "
            f"საშ. AEP {float(aep_mwh.mean()):.1f} MWh"))
        return {self.OUT_SPEED: out_speed, self.OUT_PDENS: out_pdens,
                self.OUT_AEP: out_aep}

    def tr(self, s):
        return QCoreApplication.translate("GeoEco", s)

    def name(self):
        return "wind_raster"

    def displayName(self):
        return self.tr("Wind: resource map (IDW) / ქარი: რესურსის რუკა (IDW)")

    def group(self):
        return self.tr("Energy / ენერგია")

    def groupId(self):
        return "energy"

    def shortHelpString(self):
        return self.tr(
            "წერტილოვანი სადგურებიდან IDW ინტერპოლაციით ქმნის უწყვეტ ქარის რუკებს: "
            "სიჩქარე hub-height-ზе, power density [W/m²] და AEP [MWh]. "
            "გამომავალი CRS პროექცირებული უნდა იყოს (მეტrები). "
            "რელიეფური აჩქარებისთვის → WindNinja (მომდევნო ვერსია).")

    def createInstance(self):
        return WindRasterAlgorithm()
