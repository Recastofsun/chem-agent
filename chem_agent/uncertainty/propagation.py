"""Linear propagation of uncertainties (with covariance, W-28)."""
from __future__ import annotations

import math
import numpy as np


def sigma_sum(coefs_sigmas: list[tuple[float, float]]) -> float:
    """sigma of sum(nu_i * x_i) for independent x_i."""
    return math.sqrt(sum((c * s) ** 2 for c, s in coefs_sigmas))


def sigma_sum_corr(idx_coefs: list[tuple[int, float]], sigmas: np.ndarray, 
                   sources: list[str], rho: float = 0.9) -> float:
    """sigma of sum(nu_i * x_i) with covariance by source."""
    n = len(idx_coefs)
    if n == 0:
        return 0.0
    var = 0.0
    for i in range(n):
        ci = idx_coefs[i][1]
        si = sigmas[idx_coefs[i][0]]
        var += (ci * si) ** 2
        for j in range(i + 1, n):
            cj = idx_coefs[j][1]
            sj = sigmas[idx_coefs[j][0]]
            if sources[i] == sources[j]:
                var += 2.0 * ci * cj * si * sj * rho
    return math.sqrt(max(0.0, var))


def sigma_logK(sigma_dG_kJ: float, T: float) -> float:
    """sigma of log10 K from sigma of dG (kJ/mol)."""
    return sigma_dG_kJ / (8.314462618e-3 * T * math.log(10))