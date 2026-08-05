"""
Weibull განაწილება — ქარის სიჩქარის სტატისტიკური აღწერა.

pdf:  f(v) = (k/c)·(v/c)^(k−1)·exp(−(v/c)^k)
  k = shape (ფორმა), c = scale (მასშტაბი, ≈ საშ. სიჩქარესთან).

pure math — მხოლოდ stdlib (math). numpy არ სჭირდება.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

AIR_DENSITY = 1.225  # kg/m³ (ზღვის დონე, 15°C). height/temp კორექცია → interpolation.py


@dataclass
class WeibullParams:
    k: float  # shape
    c: float  # scale [m/s]


def pdf(v, k, c):
    """ალბათობის სიმკვრივე სიჩქარეზე v."""
    if v < 0:
        return 0.0
    return (k / c) * (v / c) ** (k - 1) * math.exp(-((v / c) ** k))


def fit_moments(mean_speed: float, std_speed: float) -> WeibullParams:
    """
    მომენტების მეთოდი — საშ. სიჩქარისა და სტდ. გადახრიდან.
    k ≈ (σ/μ)^(−1.086);  c = μ / Γ(1 + 1/k).
    სწრაფი და მდგრადი, როცა მხოლოდ μ და σ გვაქვს (ტიპური სადგურის summary).
    """
    if mean_speed <= 0:
        raise ValueError("mean_speed > 0 უნდა იყოს")
    k = (std_speed / mean_speed) ** (-1.086)
    c = mean_speed / math.gamma(1 + 1 / k)
    return WeibullParams(k=k, c=c)


def fit_mle(speeds, iters: int = 100, tol: float = 1e-6) -> WeibullParams:
    """
    Maximum Likelihood fit დროითი სერიიდან (ნედლი გაზომვები).
    k იხსნება Newton-ის იტერაციით, c ანალიტიკურად.
    """
    data = [v for v in speeds if v > 0]
    n = len(data)
    if n == 0:
        raise ValueError("ცარიელი მონაცემები")
    ln = [math.log(v) for v in data]
    mean_ln = sum(ln) / n
    k = 2.0  # საწყისი
    for _ in range(iters):
        vk = [v ** k for v in data]
        sum_vk = sum(vk)
        sum_vk_ln = sum(vk[i] * ln[i] for i in range(n))
        # f(k) = sum(v^k ln v)/sum(v^k) − 1/k − mean_ln
        f = sum_vk_ln / sum_vk - 1 / k - mean_ln
        sum_vk_ln2 = sum(vk[i] * ln[i] ** 2 for i in range(n))
        fprime = (sum_vk_ln2 * sum_vk - sum_vk_ln ** 2) / sum_vk ** 2 + 1 / k ** 2
        k_new = k - f / fprime
        if abs(k_new - k) < tol:
            k = k_new
            break
        k = k_new
    c = (sum(v ** k for v in data) / n) ** (1 / k)
    return WeibullParams(k=k, c=c)


def mean_speed(p: WeibullParams) -> float:
    """განაწილების საშ. სიჩქარე = c·Γ(1 + 1/k)."""
    return p.c * math.gamma(1 + 1 / p.k)


def power_density(p: WeibullParams, air_density: float = AIR_DENSITY) -> float:
    """
    ქარის სიმძლავრის სიმკვრივე [W/m²] = ½·ρ·c³·Γ(1 + 3/k).
    ესაა რესურსის მთავარი მაჩვენებელი (ტურბინისგან დამოუკიდებელი).
    """
    return 0.5 * air_density * p.c ** 3 * math.gamma(1 + 3 / p.k)
