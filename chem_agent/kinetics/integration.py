"""Concentration vs time for the main reaction, thermodynamically consistent approach to equilibrium.

Model: overall extent xi(t) with rate  r = k * c_A * c_B * (1 - xi/xi_eq)  (second order) or
r = k * c_A * (1 - xi/xi_eq) (first order). xi_eq comes from Gibbs minimization, so the
kinetic curve ends exactly at the equilibrium composition.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.integrate import solve_ivp


def integrate(k: float, order: int, cA0: float, cB0: float, xi_eq: float, t_end: float | None = None,
              n_points: int = 50) -> dict:
    """All concentrations in mol/L; returns times and extent profile."""
    if xi_eq <= 0 or k <= 0:
        return {"t_s": [0.0], "extent_M": [0.0], "half_life_s": None}

    def rhs(_t, y):
        xi = min(max(y[0], 0.0), xi_eq)
        a = max(cA0 - xi, 0.0)
        b = max(cB0 - xi, 0.0)
        drive = max(1.0 - xi / xi_eq, 0.0)
        r = k * a * (b if order >= 2 else 1.0) * drive
        return [r]

    rate0 = rhs(0, [0.0])[0]
    if t_end is None:
        t_end = 10.0 * xi_eq / max(rate0, 1e-300)
    t_end = min(max(t_end, 1e-12), 1e12)
    ts = np.concatenate([[0.0], np.geomspace(t_end * 1e-4, t_end, n_points - 1)])
    sol = solve_ivp(rhs, (0.0, t_end), [0.0], t_eval=ts, method="LSODA", rtol=1e-8, atol=1e-14 * max(1, xi_eq))
    xi = np.clip(sol.y[0], 0.0, xi_eq)
    half = None
    target = 0.5 * xi_eq
    idx = np.where(xi >= target)[0]
    if len(idx):
        j = int(idx[0])
        if j == 0:
            half = 0.0
        else:
            t0, t1, x0, x1 = ts[j - 1], ts[j], xi[j - 1], xi[j]
            half = float(t0 + (target - x0) * (t1 - t0) / max(x1 - x0, 1e-300))
    return {"t_s": [float(t) for t in ts], "extent_M": [float(x) for x in xi], "half_life_s": half}


def analytic_half_life(k: float, order: int, cA0: float, cB0: float) -> float | None:
    """Half-life of irreversible reaction (limiting reagent)."""
    if k <= 0:
        return None
    if order <= 1:
        return math.log(2) / k
    if abs(cA0 - cB0) < 1e-12 * max(cA0, cB0):
        return 1.0 / (k * cA0)
    a, b = min(cA0, cB0), max(cA0, cB0)
    return math.log((b - a / 2) / (b) * a / (a / 2)) / (k * (b - a))
