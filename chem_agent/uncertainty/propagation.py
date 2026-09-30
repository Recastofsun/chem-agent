"""Linear propagation of uncertainties (independent errors)."""
from __future__ import annotations

import math


def sigma_sum(coefs_sigmas: list[tuple[float, float]]) -> float:
    """sigma of sum(nu_i * x_i) for independent x_i."""
    return math.sqrt(sum((c * s) ** 2 for c, s in coefs_sigmas))


def sigma_logK(sigma_dG_kJ: float, T: float) -> float:
    """sigma of log10 K from sigma of dG (kJ/mol)."""
    return sigma_dG_kJ / (8.314462618e-3 * T * math.log(10))
