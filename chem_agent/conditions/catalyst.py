"""Catalyst: does not change the equilibrium (thermodynamics), only the rate."""
from __future__ import annotations


def describe(catalyst: dict | None) -> str | None:
    if not catalyst or not catalyst.get("formula"):
        return None
    txt = f"Катализатор {catalyst['formula']}"
    if catalyst.get("loading_mol_percent"):
        txt += f" ({catalyst['loading_mol_percent']} мол. %)"
    txt += (": равновесный состав от катализатора не зависит. Влияние на скорость учитывается, "
            "только если задан барьер catalyst.barrier_kJ_mol")
    return txt
