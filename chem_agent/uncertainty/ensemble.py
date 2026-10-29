"""Monte Carlo ensemble over tabulated energies with covariance by data source (W-28)."""
from __future__ import annotations

import numpy as np

SIZES = {"fast": 8, "balanced": 24, "accurate": 64}


def draws(sigmas_rt: np.ndarray, n: int, seed: int, distribution: str = "normal", 
          sources: list[str] | None = None, rho: float = 0.9) -> np.ndarray:
    rng = np.random.default_rng(seed)
    N = len(sigmas_rt)

    if sources is None:
        if distribution == "uniform":
            half = np.sqrt(3.0) * sigmas_rt
            return rng.uniform(-half, half, size=(n, N))
        return rng.normal(0.0, 1.0, size=(n, N)) * sigmas_rt

    if distribution == "uniform":
        # Для uniform-распределения (bootstrap) ковариацию без копул не сделать, оставляем независимые
        half = np.sqrt(3.0) * sigmas_rt
        return rng.uniform(-half, half, size=(n, N))

    out = np.zeros((n, N))
    groups = {}
    for i, s in enumerate(sources):
        groups.setdefault(s, []).append(i)

    for src, idx in groups.items():
        if len(idx) == 1:
            out[:, idx] = rng.normal(0.0, 1.0, size=(n, 1)) * sigmas_rt[idx]
        else:
            sig_block = sigmas_rt[idx]
            K = len(idx)
            # Матрица ковариации: (1-rho)*diag + rho*outer
            cov_block = (1.0 - rho) * np.diag(sig_block**2) + rho * np.outer(sig_block, sig_block)
            try:
                L = np.linalg.cholesky(cov_block)
            except np.linalg.LinAlgError:
                cov_block += np.eye(K) * 1e-8
                L = np.linalg.cholesky(cov_block)
            
            Z = rng.normal(0.0, 1.0, size=(n, K))
            out[:, idx] = Z @ L.T
            
    return out


def summarize(values: list[float]) -> dict:
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if not len(a):
        return {"mean": None, "std": None, "p05": None, "p95": None, "n": 0}
    return {"mean": float(a.mean()), "std": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "p05": float(np.percentile(a, 5)), "p95": float(np.percentile(a, 95)), "n": int(len(a))}