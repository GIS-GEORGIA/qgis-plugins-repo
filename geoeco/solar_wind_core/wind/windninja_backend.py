"""
WindNinja backend (გზა A) — რელიეფ-გამZ ქარის ველი.

WindNinja (US Forest Service, ღია) — mass-conserving / momentum solver.
ჩვენ მას ხელახლა არ ვწერთ (north star) — ვახვევთ CLI-ს.

სტატუსი: STUB — WindNinja_cli შენს სისტემაზე ჯერ არ არის დაინსტალირებული.
დეტალური დიზაინი: WIND_DESIGN.md, §3.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class WindNinjaRequest:
    dem_path: str
    output_dir: str
    input_speed: float          # domain-average სიჩქარე [m/s]
    input_direction: float      # მიმართულება [deg, 0=N]
    input_height: float = 10.0  # საწყისი გაზომვის სიმაღლე [m]
    output_height: float = 80.0 # hub height [m]
    mesh_resolution: float = 100.0
    momentum_solver: bool = False  # True → უფრო ზუსტი, ნელი


def find_windninja() -> str | None:
    env = os.environ.get("WINDNINJA_CLI")
    if env and os.path.exists(env):
        return env
    for base in (
        r"C:\Program Files\WindNinja\bin\WindNinja_cli.exe",
        r"C:\WindNinja\bin\WindNinja_cli.exe",
    ):
        if os.path.exists(base):
            return base
    return shutil.which("WindNinja_cli")


def run(req: WindNinjaRequest, cli: str | None = None) -> dict:
    """
    WindNinja domain-average სცენარის გაშვება.
    აბრუნებს {'speed': path, 'direction': path} output რასტრებს.
    """
    cli = cli or find_windninja()
    if not cli:
        raise RuntimeError(
            "WindNinja_cli ვერ მოიძებნა — დააინსტალირე ან მიუთითე WINDNINJA_CLI. / "
            "WindNinja_cli not found. See WIND_DESIGN.md §3.")

    os.makedirs(req.output_dir, exist_ok=True)
    cmd = [
        cli,
        "--initialization_method", "domainAverageInitialization",
        "--elevation_file", req.dem_path,
        "--input_speed", str(req.input_speed),
        "--input_speed_units", "mps",
        "--input_direction", str(req.input_direction),
        "--input_wind_height", str(req.input_height),
        "--units_input_wind_height", "m",
        "--output_wind_height", str(req.output_height),
        "--units_output_wind_height", "m",
        "--vegetation", "grass",
        "--mesh_resolution", str(req.mesh_resolution),
        "--units_mesh_resolution", "m",
        "--write_ascii_output", "true",
        "--output_path", req.output_dir,
        "--momentum_flag", "true" if req.momentum_solver else "false",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"WindNinja ჩავარდა:\n{proc.stderr or proc.stdout}")
    return _collect_outputs(req.output_dir)


def _collect_outputs(output_dir: str) -> dict:
    result = {}
    for f in os.listdir(output_dir):
        low = f.lower()
        if low.endswith(("_vel.asc", "_spd.asc")):
            result["speed"] = os.path.join(output_dir, f)
        elif low.endswith("_ang.asc") or low.endswith("_dir.asc"):
            result["direction"] = os.path.join(output_dir, f)
    return result
