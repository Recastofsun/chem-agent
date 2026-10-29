"""Standard Gibbs energies at temperature T with Cp integration (W-02).

Three levels of accuracy:
  1. No dSf, no Cp: Gf(T) = Gf(298) (constant). Big uncertainty.
  2. dSf but no Cp: Ulich approximation, Gf(T) = Gf(298) - (T-298)*dSf/1000.
  3. dSf and Cp: full integration,
     Gf(T) = Gf(298) - (T-298)*dSf/1000 + Cp/1000 * [(T-298) - T*ln(T/298)].
"""
from __future__ import annotations

import math

from ..energy.database import Species

R = 8.314462618e-3  # kJ/(mol K)
T0 = 298.15

SIGMA_DS_KNOWN = 0.002   # kJ/(mol K): uncertainty of dSf when dHf and dGf are tabulated
SIGMA_DS_UNKNOWN = 0.10  # kJ/(mol K): no enthalpy -> temperature dependence unknown
SIGMA_CP_REL = 0.05      # 5% relative uncertainty when using Cp (typical for CRC)


def _cp_correction(Cp: float, T: float) -> float:
    """
    Возвращает Cp-поправку к Gf в кДж/моль:
        Cp/1000 * [(T - T0) - T*ln(T/T0)]
    Cp в Дж/(моль·К), T в K.
    """
    dT = T - T0
    return Cp / 1000.0 * (dT - T * math.log(T / T0))


def dGf_T(sp: Species, T: float) -> tuple[float, float, bool]:
    """
    Возвращает (dGf(T) kJ/mol, sigma kJ/mol, has_T_dependence).

    Три уровня точности (см. модуль docstring).
    """
    if sp.dGf is None:
        raise ValueError(f"Нет энергии Гиббса для {sp.id}")

    dT = T - T0
    if abs(dT) < 1e-9:
        return sp.dGf, sp.sigma, True

    # Уровень 3: полная интеграция с Cp (самый точный)
    if sp.dSf is not None and sp.Cp is not None:
        corr = _cp_correction(sp.Cp, T)
        g = sp.dGf - dT * sp.dSf / 1000.0 + corr
        sigma = sp.sigma + abs(corr) * SIGMA_CP_REL
        return g, sigma, True

    # Уровень 2: Ulich (без Cp)
    if sp.dSf is not None:
        return (
            sp.dGf - dT * sp.dSf / 1000.0,
            sp.sigma + abs(dT) * SIGMA_DS_KNOWN,
            True,
        )

    # Аномальный случай: только Cp, без dSf (редко, но бывает для простых веществ)
    if sp.Cp is not None:
        corr = _cp_correction(sp.Cp, T)
        return sp.dGf + corr, sp.sigma + abs(corr) * SIGMA_CP_REL, True

    # Уровень 1: нет данных о T-зависимости
    return sp.dGf, sp.sigma + abs(dT) * SIGMA_DS_UNKNOWN, False


def dHf_of(sp: Species) -> float | None:
    return sp.dHf


def mu0_over_RT(sp: Species, T: float) -> float:
    g, _, _ = dGf_T(sp, T)
    return g / (R * T)