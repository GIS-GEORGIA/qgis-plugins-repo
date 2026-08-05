"""
Wind Resource algorithm — წერტილოვანი ფენა (მეტეო-სადგურები / კანდიდატი საიტები)
→ თითო წერტილზე ქარის რესურსი, წლიური ენერგია (AEP) და შემოსავალი.

"ბოლო მილი" ქარისთვის: ცნობილი საშ. სიჩქარიდან → Weibull → power curve → AEP → ₾.
სრული მათემატიკა solar_wind_core.wind-შია (QGIS-ის გარეშე ტესტირებადი).

შენიშვნა: ეს არის წერტილ-დაფუძნებული screening. სივრცული ინტერპოლაცია (IDW/Kriging)
რასტრზე და WindNinja რელიეფური ველი — v0.5+ (იხ. WIND_DESIGN.md).
"""
from __future__ import annotations

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessing,
    QgsField,
    QgsFields,
    QgsFeature,
)
from qgis.PyQt.QtCore import QCoreApplication, QVariant

from solar_wind_core.wind import weibull, power_curve, interpolation


class WindResourceAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    SPEED_FIELD = "SPEED_FIELD"
    STD_FIELD = "STD_FIELD"
    K_FIXED = "K_FIXED"
    MEAS_H = "MEAS_H"
    HUB_H = "HUB_H"
    ALPHA = "ALPHA"
    RATED = "RATED"
    CUT_IN = "CUT_IN"
    RATED_SPEED = "RATED_SPEED"
    CUT_OUT = "CUT_OUT"
    TARIFF = "TARIFF"
    OUTPUT = "OUTPUT"

    # output ველები (name, type)
    _OUT_FIELDS = [
        ("v_hub", QVariant.Double),        # სიჩქარე hub height-ზე [m/s]
        ("weibull_k", QVariant.Double),
        ("weibull_c", QVariant.Double),
        ("pdens_wm2", QVariant.Double),    # power density [W/m²]
        ("aep_mwh", QVariant.Double),      # წლიური ენერგია [MWh]
        ("cf_pct", QVariant.Double),       # capacity factor [%]
        ("revenue_gel", QVariant.Double),  # წლიური შემოსავალი [₾]
    ]

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr("სადგურები / კანდიდატი საიტები (წერტილები)"),
            [QgsProcessing.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterField(
            self.SPEED_FIELD, self.tr("საშ. ქარის სიჩქარის ველი [m/s]"),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.STD_FIELD, self.tr("სტდ. გადახრის ველი [m/s] (არჩ. — ცარიელი → k ფიქს.)"),
            parentLayerParameterName=self.INPUT, optional=True,
            type=QgsProcessingParameterField.Numeric))
        self._num(self.K_FIXED, "Weibull k (თუ std არ არის)", 2.0)
        self._num(self.MEAS_H, "გაზომვის სიმაღლე [m]", 10.0)
        self._num(self.HUB_H, "Hub height [m]", 80.0)
        self._num(self.ALPHA, "Wind shear exponent α", 0.14)
        self._num(self.RATED, "ტურბინის rated power [kW]", 2000.0)
        self._num(self.CUT_IN, "Cut-in speed [m/s]", 3.0)
        self._num(self.RATED_SPEED, "Rated speed [m/s]", 12.0)
        self._num(self.CUT_OUT, "Cut-out speed [m/s]", 25.0)
        self._num(self.TARIFF, "ტარიფი [₾/kWh] (0 → გამოტოვება)", 0.0)
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr("ქარის რესურსი (წერტილები)")))

    def _num(self, name, label, default):
        self.addParameter(QgsProcessingParameterNumber(
            name, self.tr(label), defaultValue=default,
            type=QgsProcessingParameterNumber.Double))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        speed_field = self.parameterAsString(parameters, self.SPEED_FIELD, context)
        std_field = self.parameterAsString(parameters, self.STD_FIELD, context)
        k_fixed = self.parameterAsDouble(parameters, self.K_FIXED, context)
        meas_h = self.parameterAsDouble(parameters, self.MEAS_H, context)
        hub_h = self.parameterAsDouble(parameters, self.HUB_H, context)
        alpha = self.parameterAsDouble(parameters, self.ALPHA, context)
        rated = self.parameterAsDouble(parameters, self.RATED, context)
        cut_in = self.parameterAsDouble(parameters, self.CUT_IN, context)
        rated_sp = self.parameterAsDouble(parameters, self.RATED_SPEED, context)
        cut_out = self.parameterAsDouble(parameters, self.CUT_OUT, context)
        tariff = self.parameterAsDouble(parameters, self.TARIFF, context)

        # output schema = input fields + computed fields
        out_fields = QgsFields(source.fields())
        for name, qtype in self._OUT_FIELDS:
            out_fields.append(QgsField(name, qtype))

        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            source.wkbType(), source.sourceCrs())

        curve = power_curve.PowerCurve(rated_power_kw=rated, cut_in=cut_in,
                                       rated=rated_sp, cut_out=cut_out)
        ratio = (hub_h / meas_h) ** alpha if meas_h > 0 else 1.0

        total = source.featureCount() or 0
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            v_meas = feat[speed_field]
            out = QgsFeature(out_fields)
            out.setGeometry(feat.geometry())
            attrs = list(feat.attributes())

            if v_meas is None or v_meas <= 0:
                out.setAttributes(attrs + [None] * len(self._OUT_FIELDS))
                sink.addFeature(out)
                continue

            v_hub = interpolation.height_correction(v_meas, meas_h, hub_h, alpha)

            std = feat[std_field] if std_field else None
            if std not in (None, "") and float(std) > 0:
                params = weibull.fit_moments(v_hub, float(std) * ratio)
            else:
                params = weibull.from_mean_k(v_hub, k_fixed)

            pdens = weibull.power_density(params)
            aep = power_curve.aep_kwh(params, curve)           # kWh
            cf = power_curve.capacity_factor(aep, rated) * 100  # %
            revenue = aep * tariff if tariff > 0 else None

            out.setAttributes(attrs + [
                round(v_hub, 3), round(params.k, 3), round(params.c, 3),
                round(pdens, 1), round(aep / 1000.0, 2), round(cf, 1),
                round(revenue, 2) if revenue is not None else None,
            ])
            sink.addFeature(out)
            if total:
                feedback.setProgress(100 * (i + 1) / total)

        return {self.OUTPUT: dest_id}

    def tr(self, s):
        return QCoreApplication.translate("GeoEco", s)

    def name(self):
        return "wind_resource"

    def displayName(self):
        return self.tr("Wind: resource & yield / ქარი: რესურსი და გამომუშავება")

    def group(self):
        return self.tr("Energy / ენერგია")

    def groupId(self):
        return "energy"

    def shortHelpString(self):
        return self.tr(
            "წერტილოვანი ფენიდან (საშ. ქარის სიჩქარით) ითვლის Weibull-ს, "
            "power density-ს, წლიურ ენერგიას (AEP), capacity factor-ს და შემოსავალს. "
            "სიმაღლური კორექცია power-law-ით (α). std ველი არჩევითია.")

    def createInstance(self):
        return WindResourceAlgorithm()
