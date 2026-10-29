"""Eyring equation (transition state theory)."""
from __future__ import annotations

import math

KB = 1.380649e-23      # J/K
H_PLANCK = 6.62607015e-34
R_J = 8.314462618      # J/(mol K)


def rate_constant(barrier_kJ_mol: float, T: float, kappa: float = 1.0) -> float:
    """k = kappa * kB*T/h * exp(-dG_act / RT), s^-1 (first order) or M^-1 s^-1 with c0 = 1 M."""
    return kappa * KB * T / H_PLANCK * math.exp(-barrier_kJ_mol * 1000.0 / (R_J * T))


def barrier_from_rate(k: float, T: float) -> float:
    return -R_J * T * math.log(k * H_PLANCK / (KB * T)) / 1000.0


def rate_constant_sigma(barrier_kJ_mol: float, sigma_kJ: float, T: float) -> tuple[float, float]:
    """Return (k, relative factor) for 1-sigma barrier uncertainty: k in [k/f, k*f]."""
    k = rate_constant(barrier_kJ_mol, T)
    f = math.exp(sigma_kJ * 1000.0 / (R_J * T))
    return k, f
