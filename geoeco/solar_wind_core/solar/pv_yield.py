"""
PV yield — რადიაცია → ელექტროენერგია.

მუშაობს როგორც სკალარზე (ერთი ლოკაცია), ისე numpy მასივზე (რასტრი),
რადგან ყველა ოპერაცია ელემენტ-ბაი-ელემენტია. GDAL/numpy აქ არ არის სავალდებულო.

ორი სტანდარტული მეთოდი:
  1) area_method   — ცნობილია ფართი (მ²) და მოდულის efficiency.
  2) kwp_method    — ცნობილია დადგმული სიმძლავრე (kWp). PVGIS-ის სტანდარტი.

ორივეს გული: Performance Ratio (PR) — რეალური დანაკარგები (temp, inverter,
cabling, soiling, mismatch). ტიპური PR ≈ 0.75.
"""
from __future__ import annotations

G_STC = 1.0  # kW/m² — standard test condition irradiance (1000 W/m²)


def energy_area_method(radiation_kwh_m2, area_m2, module_eff=0.20, pr=0.75):
    """
    E = H · A · η · PR

    radiation_kwh_m2 : წლიური (ან პერიოდის) in-plane რადიაცია [kWh/m²]
                       (SAGA/GRASS output). float ან numpy array.
    area_m2          : პანელების ჯამური ფართი [m²]
    module_eff       : მოდულის efficiency (0..1), მაგ. 0.20 = 20%
    pr               : Performance Ratio (0..1)
    returns          : ენერგია [kWh] (იგივე ტიპი, რაც radiation)
    """
    return radiation_kwh_m2 * area_m2 * module_eff * pr


def energy_kwp_method(radiation_kwh_m2, kwp, pr=0.75):
    """
    E = kWp · (H / G_stc) · PR   —  PVGIS-ის სტანდარტული ფორმულა.

    radiation_kwh_m2 : in-plane რადიაცია [kWh/m²]
    kwp              : დადგმული პიკური სიმძლავრე [kWp]
    pr               : Performance Ratio
    returns          : ენერგია [kWh]
    """
    return kwp * (radiation_kwh_m2 / G_STC) * pr


def specific_yield(radiation_kwh_m2, pr=0.75):
    """
    Specific yield [kWh/kWp] — ინდუსტრიის შესადარებელი მაჩვენებელი.
    = (H / G_stc) · PR. საქართველოში ტიპურად ~1200-1500 kWh/kWp.
    """
    return (radiation_kwh_m2 / G_STC) * pr


def co2_avoided(energy_kwh, grid_factor_kg_per_kwh=0.12):
    """
    აცილებული CO₂ [kg]. საქართველოს ბადის ფაქტორი დაბალია (ჰიდრო),
    ~0.12 kgCO₂/kWh (default, პარამეტrიზებადი).
    """
    return energy_kwh * grid_factor_kg_per_kwh
