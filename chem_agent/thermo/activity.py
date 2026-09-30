"""Activity coefficient models for aqueous solutes (molal scale)."""
from __future__ import annotations

import math

import numpy as np

LN10 = math.log(10.0)
MODELS = ("ideal", "debye_huckel", "davies", "pitzer")


def water_density(T: float) -> float:
    """g/cm3, Thiesen-type correlation, valid 0-100 C (clipped outside)."""
    t = min(max(T - 273.15, 0.0), 150.0)
    return 1 - (t + 288.9414) / (508929.2 * (t + 68.12963)) * (t - 3.9863) ** 2


def water_dielectric(T: float) -> float:
    """Malmberg & Maryott (1956), 0-100 C."""
    t = min(max(T - 273.15, 0.0), 150.0)
    return 87.740 - 0.40008 * t + 9.398e-4 * t ** 2 - 1.410e-6 * t ** 3


def dh_constants(T: float, eps: float | None = None, rho: float | None = None) -> tuple[float, float]:
    """Debye-Huckel A (kg^0.5 mol^-0.5, log10) and B (kg^0.5 mol^-0.5 A^-1)."""
    eps = eps or water_dielectric(T)
    rho = rho or water_density(T)
    A = 1.82483e6 * math.sqrt(rho) / (eps * T) ** 1.5
    B = 50.2916 * math.sqrt(rho) / math.sqrt(eps * T)
    return A, B


def make_gamma_fn(model: str, T: float, eps: float | None = None, ion_size_A: float = 4.0):
    """Return f(I, charges) -> ln(gamma) array; None for ideal."""
    if model == "ideal":
        return None
    A, B = dh_constants(T, eps)
    if model == "debye_huckel":
        def f(I, z):
            sI = math.sqrt(max(I, 0.0))
            return -LN10 * A * np.asarray(z) ** 2 * sI / (1.0 + B * ion_size_A * sI)
        return f
    if model in ("davies", "pitzer"):
        def f(I, z):
            sI = math.sqrt(max(I, 0.0))
            return -LN10 * A * np.asarray(z) ** 2 * (sI / (1.0 + sI) - 0.3 * I)
        return f
    raise ValueError(f"Неизвестная модель активности: {model}")


def validity_warning(model: str, I: float) -> str | None:
    if model == "debye_huckel" and I > 0.15:
        return f"Ионная сила {I:.2f}".replace(".", ",") + " М выше области применимости расширенного Дебая-Хюккеля (~0,1 М)"
    if model in ("davies", "pitzer") and I > 0.6:
        return f"Ионная сила {I:.2f}".replace(".", ",") + " М выше области применимости модели Дэвиса (~0,5 М); коэффициенты активности приблизительны"
    return None
