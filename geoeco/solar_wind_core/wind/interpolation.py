"""
სივრცული ინტერპოლაცია + სიმაღლური კორექცია (გზა B).

სადგურის წერტილოვანი მონაცემები → უწყვეტი ქარის ველი.
  1) სიმაღლური კორექცია hub height-მდე (power law).
  2) სივრცული ინტერპოლაცია (IDW MVP; Kriging → pykrige, v0.4+).

MVP: IDW pure-python (numpy optional). Kriging/რასტრიზაცია — v0.4.
დეტალები: WIND_DESIGN.md.
"""
from __future__ import annotations

import math


def height_correction(v_ref: float, h_ref: float, h_target: float,
                      alpha: float = 0.14) -> float:
    """
    Wind profile power law:  v(h) = v_ref · (h_target / h_ref)^α.
    α: open terrain ≈0.14, ტყე/ქალაქი ≈0.25-0.40 (Hellmann exponent).
    """
    if h_ref <= 0:
        raise ValueError("h_ref > 0")
    return v_ref * (h_target / h_ref) ** alpha


def idw(x: float, y: float, stations, power: float = 2.0):
    """
    Inverse Distance Weighting ერთ წერტილში.
    stations: [(sx, sy, value), ...]. value — მაგ. საშ. სიჩქარე hub height-ზე.
    """
    num = 0.0
    den = 0.0
    for sx, sy, val in stations:
        d = math.hypot(x - sx, y - sy)
        if d == 0:
            return val
        w = 1.0 / d ** power
        num += w * val
        den += w
    return num / den if den else float("nan")


def idw_grid(stations, bounds, nx: int, ny: int, power: float = 2.0):
    """
    IDW რასტრზე. bounds=(xmin,ymin,xmax,ymax). აბრუნებს 2D სიას (ny×nx).
    numpy-ს არ მოითხოვს, მაგრამ დიდ ბადეზე ნელია → v0.4-ში numpy/scipy.
    """
    xmin, ymin, xmax, ymax = bounds
    dx = (xmax - xmin) / max(nx - 1, 1)
    dy = (ymax - ymin) / max(ny - 1, 1)
    grid = []
    for j in range(ny):
        y = ymin + j * dy
        row = [idw(xmin + i * dx, y, stations, power) for i in range(nx)]
        grid.append(row)
    return grid
