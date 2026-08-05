"""
ეკონომიკა — ენერგია → ფული. ესაა ის "ბოლო მილი", რასაც ვერცერთი GIS ძრავა იძლევა.

ყველა ფუნქცია სკალარზეც მუშაობს (ერთი ლოკაცია) და numpy მასივზეც (რასტრი).
ვალუტა: ₾ (GEL), მაგრამ არაფერია valuta-სპეციფიკური — ტარიფი პარამეტრია.
"""
from __future__ import annotations

from dataclasses import dataclass


def annual_revenue(energy_kwh, tariff_gel_per_kwh):
    """წლიური შემოსავალი/დანაზოგი [₾] = E · ტარიფი."""
    return energy_kwh * tariff_gel_per_kwh


def simple_payback_years(capex_gel, annual_net_gel):
    """
    მარტივი უკუგების ვადა [წელი] = CAPEX / წლიური_წმინდა_დანაზოგი.
    annual_net_gel = annual_revenue - annual_opex.
    """
    if annual_net_gel <= 0:
        return float("inf")
    return capex_gel / annual_net_gel


def crf(discount_rate, years):
    """
    Capital Recovery Factor — ანუიტეტის კოეფიციენტი.
    CRF = r(1+r)^n / ((1+r)^n − 1). r=0 → 1/n.
    """
    if discount_rate == 0:
        return 1.0 / years
    q = (1 + discount_rate) ** years
    return discount_rate * q / (q - 1)


def lcoe(capex_gel, annual_opex_gel, annual_energy_kwh,
         discount_rate=0.08, years=25):
    """
    Levelized Cost of Energy [₾/kWh].
    LCOE = (CAPEX · CRF + OPEX_წლ) / ენერგია_წლ.
    ენერგიაზე ხშირად რთავენ degradation-ს; MVP-ში მარტივ ვარიანტს ვიყენებთ.
    """
    if annual_energy_kwh <= 0:
        return float("inf")
    annualized_capex = capex_gel * crf(discount_rate, years)
    return (annualized_capex + annual_opex_gel) / annual_energy_kwh


def npv(capex_gel, annual_net_gel, discount_rate=0.08, years=25,
        degradation=0.005):
    """
    Net Present Value [₾].
    NPV = −CAPEX + Σ_{t=1..n} netₜ / (1+r)^t,
    სადაც netₜ მცირდება წლიური degradation-ით (პანელის დაძველება, ~0.5%/წ).
    """
    total = -capex_gel
    for t in range(1, years + 1):
        cashflow_t = annual_net_gel * ((1 - degradation) ** (t - 1))
        total += cashflow_t / ((1 + discount_rate) ** t)
    return total


@dataclass
class PVEconomicsResult:
    """ერთი ლოკაციის სრული ეკონომიკური შედეგი — რეპორტისთვის."""
    annual_energy_kwh: float
    annual_revenue_gel: float
    payback_years: float
    lcoe_gel_per_kwh: float
    npv_gel: float
    co2_avoided_kg: float


def evaluate(energy_kwh, tariff_gel_per_kwh, capex_gel,
             annual_opex_gel=0.0, discount_rate=0.08, years=25,
             grid_factor=0.12):
    """
    ერთი ლოკაციის ბოლომდე დათვლა (სკალარი) — CLI/რეპორტის მთავარი შესასვლელი.
    """
    from . import pv_yield
    rev = annual_revenue(energy_kwh, tariff_gel_per_kwh)
    net = rev - annual_opex_gel
    return PVEconomicsResult(
        annual_energy_kwh=energy_kwh,
        annual_revenue_gel=rev,
        payback_years=simple_payback_years(capex_gel, net),
        lcoe_gel_per_kwh=lcoe(capex_gel, annual_opex_gel, energy_kwh,
                              discount_rate, years),
        npv_gel=npv(capex_gel, net, discount_rate, years),
        co2_avoided_kg=pv_yield.co2_avoided(energy_kwh, grid_factor),
    )
