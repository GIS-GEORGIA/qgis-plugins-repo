"""
მარტივი ორენოვანი (ka/en) ფენა core-სთვის — რიცხვების, ლეიბლების, რეპორტების.

QGIS plugin UI იყენებს Qt-ის სტანდარტულ .ts/.qm თარგმანს (tr()).
core-ს კი Qt არ აქვს, ამიტომ აქ მსუბუქი dict-ზე დაფუძნებული t() გვაქვს,
რომ CLI/რეპორტიც ორ ენაზე მუშაობდეს.
"""
from __future__ import annotations

DEFAULT_LANG = "ka"

# key -> {lang: text}
_STRINGS: dict[str, dict[str, str]] = {
    "annual_energy": {"ka": "წლიური გამომუშავება", "en": "Annual energy"},
    "annual_revenue": {"ka": "წლიური შემოსავალი", "en": "Annual revenue"},
    "payback": {"ka": "უკუგების ვადა", "en": "Payback period"},
    "lcoe": {"ka": "ენერგიის თვითღირებულება (LCOE)", "en": "Levelized cost (LCOE)"},
    "npv": {"ka": "წმინდა მიმდინარე ღირებულება (NPV)", "en": "Net present value (NPV)"},
    "optimal_tilt": {"ka": "ოპტიმალური დახრა", "en": "Optimal tilt"},
    "optimal_azimuth": {"ka": "ოპტიმალური აზიმუტი", "en": "Optimal azimuth"},
    "mean_wind_speed": {"ka": "საშუალო ქარის სიჩქარე", "en": "Mean wind speed"},
    "wind_power_density": {"ka": "ქარის სიმძლავრის სიმკვრივე", "en": "Wind power density"},
    "capacity_factor": {"ka": "დატვირთვის კოეფიციენტი", "en": "Capacity factor"},
    "years": {"ka": "წელი", "en": "years"},
}

_UNITS = {
    "kwh": {"ka": "კვტ·სთ", "en": "kWh"},
    "mwh": {"ka": "მგვტ·სთ", "en": "MWh"},
    "gel": {"ka": "₾", "en": "GEL"},
    "gel_per_kwh": {"ka": "₾/კვტ·სთ", "en": "GEL/kWh"},
    "wm2": {"ka": "ვტ/მ²", "en": "W/m²"},
    "ms": {"ka": "მ/წმ", "en": "m/s"},
    "deg": {"ka": "°", "en": "°"},
}


def t(key: str, lang: str = DEFAULT_LANG) -> str:
    """ლეიბლის თარგმანი. უცნობი key უბრუნდება როგორც არის."""
    return _STRINGS.get(key, {}).get(lang, key)


def unit(key: str, lang: str = DEFAULT_LANG) -> str:
    return _UNITS.get(key, {}).get(lang, key)


def fmt(value: float, unit_key: str | None = None, lang: str = DEFAULT_LANG,
        digits: int = 2) -> str:
    """რიცხვის ფორმატირება ერთეულით — მაგ. '1 234.50 კვტ·სთ'."""
    s = f"{value:,.{digits}f}"
    if unit_key:
        return f"{s} {unit(unit_key, lang)}"
    return s
