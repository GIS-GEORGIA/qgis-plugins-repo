"""
ოპტიმალური დახრა/აზიმუტი — ერთადერთი ადგილი, სადაც მზეზე ცოტა მეტ ჭკუას ვდებთ.

არსებული ხელსაწყო რადიაციას მიწის ზედაპირზე ითვლის. პანელი კი დახრილია.
აქ ვუშვებთ ძრავას რამდენიმე (tilt, azimuth) კომბინაციაზე და ვირჩევთ მაქსიმუმს.

ორი რეჟიმი:
  1) engine-ზე დაფუძნებული (ზუსტი) — radiation_fn(tilt, az) → kWh/m² (SAGA/r.sun).
     radiation_fn injectable-ია → ტესტდება ძრავის გარეშე.
  2) heuristic (სწრაფი) — გრძედზე დაფუძნებული ანალიტიკური მიახლოება, fallback-ად.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class TiltResult:
    tilt_deg: float
    azimuth_deg: float
    radiation_kwh_m2: float
    gain_vs_flat_pct: float | None = None


def optimize(radiation_fn: Callable[[float, float], float],
             tilts=range(0, 61, 5),
             azimuths=(180,),
             flat_radiation: float | None = None) -> TiltResult:
    """
    ბადური ძებნა (tilt, azimuth) სივრცეში.

    radiation_fn : (tilt_deg, azimuth_deg) -> kWh/m²  (ძრავის wrapper)
    tilts        : დასათვალიერებელი დახრები
    azimuths     : აზიმუტები (180 = სამხრეთი, ჩრდ. ნახევარსფerო)
    flat_radiation: 0°-ის რადიაცია gain-ის დასათვლელად (optional)
    """
    best = None
    for az in azimuths:
        for tilt in tilts:
            rad = radiation_fn(float(tilt), float(az))
            if best is None or rad > best.radiation_kwh_m2:
                best = TiltResult(float(tilt), float(az), rad)
    if best is None:
        raise ValueError("ცარიელი ძებნის სივრცე / empty search space")
    if flat_radiation and flat_radiation > 0:
        best.gain_vs_flat_pct = 100.0 * (best.radiation_kwh_m2 - flat_radiation) / flat_radiation
    return best


def heuristic_optimal_tilt(latitude_deg: float) -> float:
    """
    სწრაფი მიახლოება ძრავის გარეშე — წლიური ოპტიმუმი.
    ემპირიული (Jacobson & Jadhav, 2018 მიახლ.): დაბალ გრძედზე tilt ≈ 0.87·|lat|,
    მაღალზე ოდნავ ნაკლები. საქართველოსთვის (~41.7°N) → ~33-35°.
    """
    lat = abs(latitude_deg)
    if lat <= 25:
        tilt = lat * 0.87
    elif lat <= 50:
        tilt = 0.76 * lat + 3.1
    else:
        tilt = 0.5 * lat + 16.3
    return round(tilt, 1)


def hemisphere_azimuth(latitude_deg: float) -> float:
    """ოპტიმალური აზიმუტი: სამხრეთი (180°) ჩრდ. ნახევარსფეროში, ჩრდ. (0°) სამხრეთში."""
    return 180.0 if latitude_deg >= 0 else 0.0
