"""Monte Carlo ensemble over tabulated energies with covariance by data source (W-28, W-35)."""
from __future__ import annotations
import numpy as np
from scipy.stats import norm

SIZES = {
    "fast": 8,
    "balanced": 24,
    "accurate": 64,
    "bayesian": 1000,  # W-35: для точных credible intervals
}

def draws(sigmas_rt: np.ndarray, n: int, seed: int, distribution: str = "normal",
          sources: list[str] | None = None, rho: float = 0.9) -> np.ndarray:
    """Генерирует n выборок из многомерного нормального/равномерного распределения."""
    rng = np.random.default_rng(seed)
    N = len(sigmas_rt)
    
    if sources is None:
        if distribution == "uniform":
            half = np.sqrt(3.0) * sigmas_rt
            return rng.uniform(-half, half, size=(n, N))
        return rng.normal(0.0, 1.0, size=(n, N)) * sigmas_rt
    
    if distribution == "uniform":
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
            cov_block = (1.0 - rho) * np.diag(sig_block**2) + rho * np.outer(sig_block, sig_block)
            try:
                L = np.linalg.cholesky(cov_block)
            except np.linalg.LinAlgError:
                cov_block += np.eye(K) * 1e-8
                L = np.linalg.cholesky(cov_block)
            Z = rng.normal(0.0, 1.0, size=(n, K))
            out[:, idx] = Z @ L.T
    
    return out


def summarize(values: list[float], confidence_level: float = 0.90) -> dict:
    """
    Статистика выборки с credible intervals.
    
    Args:
        values: список значений
        confidence_level: уровень доверия (0.90 для 90% CI, 0.95 для 95% CI)
    
    Returns:
        dict с mean, std, p05, p95, n, credible_interval
    """
    a = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if not len(a):
        return {
            "mean": None, "std": None,
            "p05": None, "p95": None,
            "credible_interval_90": None,
            "credible_interval_95": None,
            "n": 0
        }
    
    mean = float(a.mean())
    std = float(a.std(ddof=1)) if len(a) > 1 else 0.0
    
    # Перцентили для 90% CI (p05, p95)
    p05 = float(np.percentile(a, 5))
    p95 = float(np.percentile(a, 95))
    
    # Перцентили для 95% CI (p025, p975)
    p025 = float(np.percentile(a, 2.5))
    p975 = float(np.percentile(a, 97.5))
    
    return {
        "mean": mean,
        "std": std,
        "p05": p05,
        "p95": p95,
        "credible_interval_90": [p05, p95],
        "credible_interval_95": [p025, p975],
        "n": int(len(a))
    }


def analytical_credible_interval(
    mean: float,
    sigma: float,
    confidence_level: float = 0.95
) -> list[float]:
    """
    Аналитический credible interval для нормального распределения.
    
    Args:
        mean: математическое ожидание
        sigma: стандартное отклонение
        confidence_level: уровень доверия (0.95 для 95% CI)
    
    Returns:
        [lower, upper] — границы credible interval
    """
   
    z = norm.ppf(0.5 + confidence_level / 2)
    return [mean - z * sigma, mean + z * sigma]


