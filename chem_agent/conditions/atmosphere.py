"""Atmosphere above the solution: closed headspace of given volume (open system = large headspace)."""
from __future__ import annotations

from ..search.hypotheses import headspace_gas


def gas_amounts(cond: dict, T: float, include: bool = True) -> tuple[dict, list[str]]:
    atm = cond.get("atmosphere")
    notes: list[str] = []
    if not include or not atm:
        return {}, notes
    mode = atm.get("mode", "closed")
    V = float(atm.get("headspace_L", 1000.0 if mode == "open" else cond.get("volume_L") or 1.0))
    P = float(atm.get("pressure_atm", cond.get("pressure_atm", 1.0)))
    gases = headspace_gas(atm, V, P, T)
    if atm.get("humidity_percent") is not None:
        notes.append("Влажность воздуха не учитывается: испарение/конденсация воды не моделируются")
    notes.append(f"Атмосфера: газовое пространство {V:g} л над системой ({'открытая' if mode == 'open' else 'закрытая'} система)")
    return gases, notes
