"""pH: initial pH of the solvent (strong acid/base addition) and buffered (pH-stat) mode."""
from __future__ import annotations

KW = 1.0e-14


def titrant_for_initial_pH(pH: float, water_kg: float) -> tuple[str, float] | None:
    """Strong acid (HCl) or base (NaOH) amount that sets pure water to the given pH."""
    h = 10.0 ** (-pH)
    oh = KW / h
    excess = (h - oh) * water_kg
    if abs(excess) < 1e-12:
        return None
    return ("HCl", excess) if excess > 0 else ("NaOH", -excess)
