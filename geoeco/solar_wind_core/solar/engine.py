"""
Solar engine — SAGA/GRASS r.sun-ის wrapper. ფიზიკას აქ არ ვწერთ.

ორი გზა:
  A) QGIS-ის შიგნიდან → processing.run('grass:r.sun...' / 'sagang:...')
  B) standalone → საბრძანებო ხაზიდან saga_cmd.exe / r.sun.exe subprocess-ით.

ეს ფაილი აბსტrაქციას იძლევა: solar_radiation(...) აბრუნებს რადიაციის რასტრის გზას.
tilt/azimuth გადაეცემა slope/aspect რასტრებად (r.sun-ის aspin/slopein).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class SolarRequest:
    dem_path: str
    out_path: str
    day: int = 172              # წლის დღე (172 ≈ 21 ივნისი). -1 → წლიური ჯამი (SAGA)
    linke: float = 3.0          # Linke turbidity (ატმ. simკვრივე)
    albedo: float = 0.2
    tilt_deg: float | None = None      # None → მიწის ზედაპირი (DEM slope)
    azimuth_deg: float | None = None   # None → DEM aspect. 180 = სამხრეთი
    step_minutes: int = 30


def find_saga_cmd() -> str | None:
    """saga_cmd.exe-ს პოვნა QGIS-ის ინსტალაციაში ან PATH-ში."""
    env = os.environ.get("SAGA_CMD")
    if env and os.path.exists(env):
        return env
    for base in (
        r"C:\Program Files\QGIS 3.44.5\apps\saga\saga_cmd.exe",
        r"C:\Program Files\QGIS 4.2.0\apps\saga\saga_cmd.exe",
    ):
        if os.path.exists(base):
            return base
    return shutil.which("saga_cmd")


def solar_radiation_saga(req: SolarRequest, saga_cmd: str | None = None) -> str:
    """
    SAGA ta_lighting tool 2 (Potential Incoming Solar Radiation) გამოძახება.
    აბრუნებს რადიაციის რასტრის გზას (req.out_path).

    შენიშვნა: SAGA უჯრედის output ერთეული kWh/m² არის (Period=Annual, unit=kWh/m2).
    tilt/azimuth-ისთვის საჭიროა წინასწარ დამზადებული slope/aspect grid (tilt_optimizer).
    """
    saga_cmd = saga_cmd or find_saga_cmd()
    if not saga_cmd:
        raise RuntimeError(
            "saga_cmd ვერ მოიძებნა. მიუთითე SAGA_CMD env ან QGIS-ის ბილიკი. / "
            "saga_cmd not found; set SAGA_CMD env or QGIS path.")

    # SAGA-ს სჭირდება .sgrd; GeoTIFF-იდან იმპორტი/ექსპორტი gdal-ით ხდება QGIS wrapper-ში.
    # MVP: პირდაპირ ვცდით tif input-ს (SAGA >=7 კითხულობს gdal-ით).
    cmd = [
        saga_cmd, "ta_lighting", "2",
        "-GRD_DEM", req.dem_path,
        "-GRD_DIRECT", req.out_path,
        "-DAY", str(max(req.day, 1)),
        "-LINKE_TYPE", "0", "-LINKE", str(req.linke),
        "-ALBEDO", str(req.albedo),
        "-UNITS", "1",          # 1 = kWh/m²
    ]
    if req.tilt_deg is not None:
        cmd += ["-GRD_FLAT", "0"]  # გამოთვლა დახრილ ზედაპირზე (slope/aspect grid-ით)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"SAGA solar radiation ჩავარდა:\n{proc.stderr or proc.stdout}")
    return req.out_path


def solar_radiation_qgis(req: SolarRequest):
    """
    QGIS Processing-ის გავლით (r.sun ან SAGA). გამოიძახება მხოლოდ ფლაგინის შიგნით,
    სადაც `processing` და `qgis.core` ხელმისაწვდომია.
    """
    import processing  # QGIS-only
    params = {
        "elevation": req.dem_path,
        "day": max(req.day, 1),
        "step": req.step_minutes / 60.0,
        "linkevalue": req.linke,
        "albedovalue": req.albedo,
        "-p": True,  # კუმულაციური რადიაცია
        "glob_rad": req.out_path,
    }
    if req.tilt_deg is not None:
        params["slope_value"] = req.tilt_deg
    if req.azimuth_deg is not None:
        params["aspect_value"] = req.azimuth_deg
    processing.run("grass:r.sun.incidout", params)
    return req.out_path
