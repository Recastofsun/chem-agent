"""Standard Gibbs energies at temperature T and their uncertainties."""
from __future__ import annotations

from ..energy.database import Species

R = 8.314462618e-3  # kJ/(mol K)
T0 = 298.15

SIGMA_DS_KNOWN = 0.002   # kJ/(mol K): uncertainty of dSf when dHf and dGf are tabulated
SIGMA_DS_UNKNOWN = 0.10  # kJ/(mol K): no enthalpy -> temperature dependence unknown


def dGf_T(sp: Species, T: float) -> tuple[float, float, bool]:
    """Return (dGf(T) kJ/mol, sigma kJ/mol, has_T_dependence).

    Constant dHf, dSf approximation (Ulich / Ellingham): dGf(T) = dGf(T0) - (T - T0) * dSf.
    Conventions of ions (H+ = 0) and elements cancel in element-conserving minimization.
    """
    if sp.dGf is None:
        raise ValueError(f"Нет энергии Гиббса для {sp.id}")
    dT = T - T0
    if abs(dT) < 1e-9:
        return sp.dGf, sp.sigma, True
    if sp.dSf is not None:
        return sp.dGf - dT * sp.dSf / 1000.0, sp.sigma + abs(dT) * SIGMA_DS_KNOWN, True
    return sp.dGf, sp.sigma + abs(dT) * SIGMA_DS_UNKNOWN, False


def dHf_of(sp: Species) -> float | None:
    return sp.dHf


def mu0_over_RT(sp: Species, T: float) -> float:
    g, _, _ = dGf_T(sp, T)
    return g / (R * T)
