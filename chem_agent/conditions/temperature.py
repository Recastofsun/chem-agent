"""Temperature: main value, profiles (ramp / constant / points) and sampling."""
from __future__ import annotations

import numpy as np


def profile_points(cond: dict) -> list[dict]:
    """[{T_K, t_s}] along the temperature profile; [] if no profile."""
    prof = cond.get("temperature_profile")
    n = int((cond.get("time") or {}).get("sample_points", 10))
    if not prof:
        return []
    t = prof.get("type", "ramp")
    if t == "constant":
        return [{"T_K": float(cond["temperature_K"]), "t_s": 0.0}]
    if t == "points":
        return [{"T_K": float(p), "t_s": None} for p in prof.get("points_K", [])]
    a, b = float(prof["start_K"]), float(prof["end_K"])
    rate = float(prof.get("rate_K_per_min", 5.0))
    Ts = np.linspace(a, b, max(2, n))
    return [{"T_K": float(T), "t_s": float(abs(T - a) / rate * 60.0)} for T in Ts]


def scan_range(T: float, width: float = 75.0, n: int = 16) -> list[float]:
    lo = max(200.0, T - width)
    return [float(x) for x in np.linspace(lo, T + width, n)]
