"""
Solar მოდული — ფიზიკას არ ვწერთ.

engine.py        → SAGA/GRASS r.sun გამოძახება (რადიაციის რასტრი kWh/m²/yr)
pv_yield.py      → რადიაცია → ელ. ენერგია (kWh)
economics.py     → ენერგია → ფული (₾), payback, LCOE, NPV
tilt_optimizer.py→ ოპტიმალური tilt/azimuth (r.sun-ს slope/aspect input-ს ვასესხებთ)
"""
from . import pv_yield, economics, tilt_optimizer  # noqa: F401

__all__ = ["engine", "pv_yield", "economics", "tilt_optimizer"]
