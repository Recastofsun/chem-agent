"""Monte Carlo ensemble over tabulated energies.

Each member draws dGf_i(T) ~ N(nominal, sigma_i(T)) independently (seeded, deterministic) and
re-solves the equilibrium. Spread of results = uncertainty; the share of members that keep the
nominal main product = confidence.
"""
from __future__ import annotations

import numpy as np

SIZES = {"fast": 8, "balanced": 24, "accurate": 64}


def draws(sigmas_rt: np.ndarray, n: int, seed: int, distribution: str = "normal") -> np.ndarray:
    rng = np.random.default_rng(seed)
    if distribution == "uniform":  # bootstrap-like alternative with the same variance
        half = np.sqrt(3.0) * sigmas_rt
        return rng.uniform(-half, half, size=(n, len(sigmas_rt)))
    return rng.normal(0.0, 1.0, size=(n, len(sigmas_rt))) * sigmas_rt


def summarize(values: list[float]) -> dict:
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if not len(a):
        return {"mean": None, "std": None, "p05": None, "p95": None, "n": 0}
    return {"mean": float(a.mean()), "std": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "p05": float(np.percentile(a, 5)), "p95": float(np.percentile(a, 95)), "n": int(len(a))}
