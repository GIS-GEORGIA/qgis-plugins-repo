"""
ტურბინის power curve + წლიური ენერგია (AEP).

AEP = 8760 · ∫ f(v)·P(v) dv,  სადაც f(v) — Weibull pdf, P(v) — power curve.
ინტეგრალს რიცხვითად ვითვლით (ტrapezoid) 0..cutout დიაპაზონში.

pure math — stdlib მხოლოდ.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HOURS_PER_YEAR = 8760.0


@dataclass
class PowerCurve:
    """
    გამარტივებული ანალიტიკური power curve.
    v < cut_in:              0
    cut_in ≤ v < rated:      კუბური ზრდა rated_power-მდე
    rated ≤ v < cut_out:     rated_power
    v ≥ cut_out:             0 (უსაფრთხოების გაჩერება)
    """
    rated_power_kw: float
    cut_in: float = 3.0
    rated: float = 12.0
    cut_out: float = 25.0

    def power(self, v: float) -> float:
        if v < self.cut_in or v >= self.cut_out:
            return 0.0
        if v < self.rated:
            # კუბური ინტერპოლაცია cut_in..rated შორის
            frac = (v ** 3 - self.cut_in ** 3) / (self.rated ** 3 - self.cut_in ** 3)
            return self.rated_power_kw * frac
        return self.rated_power_kw


@dataclass
class TabulatedCurve:
    """მწარმოებლის ცხრილი: (სიჩქარე, სიმძლავრე_kW) წყვილები. წრფივი ინტერპოლაცია."""
    points: list  # [(v, kw), ...] ზრდადი v-ით
    _v: list = field(default_factory=list, repr=False)
    _p: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        pts = sorted(self.points)
        self._v = [p[0] for p in pts]
        self._p = [p[1] for p in pts]

    def power(self, v: float) -> float:
        if v <= self._v[0] or v >= self._v[-1]:
            return 0.0
        for i in range(1, len(self._v)):
            if v <= self._v[i]:
                v0, v1 = self._v[i - 1], self._v[i]
                p0, p1 = self._p[i - 1], self._p[i]
                return p0 + (p1 - p0) * (v - v0) / (v1 - v0)
        return 0.0


def aep_kwh(weibull_params, curve, v_max: float = 30.0, step: float = 0.25) -> float:
    """
    წლიური ენერგია [kWh] Weibull პარამეტრებისა და power curve-ისთვის.

    weibull_params : wind.weibull.WeibullParams
    curve          : ობიექტი .power(v) მეთოდით (PowerCurve/TabulatedCurve)
    ტrapezoid ინტეგრება 0..v_max, ბიჯით step.
    """
    from . import weibull as wb
    k, c = weibull_params.k, weibull_params.c
    n = int(v_max / step)
    total = 0.0
    prev = wb.pdf(0.0, k, c) * curve.power(0.0)
    for i in range(1, n + 1):
        v = i * step
        cur = wb.pdf(v, k, c) * curve.power(v)
        total += 0.5 * (prev + cur) * step
        prev = cur
    return total * HOURS_PER_YEAR


def capacity_factor(aep_kwh_value: float, rated_power_kw: float) -> float:
    """დატვირთვის კოეფიციენტი = AEP / (Prated · 8760). ტიპური onshore ~0.25-0.45."""
    denom = rated_power_kw * HOURS_PER_YEAR
    return aep_kwh_value / denom if denom > 0 else 0.0
