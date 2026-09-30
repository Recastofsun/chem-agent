"""Solvent: water properties and amount of water in the system."""
from __future__ import annotations

from ..parser.formula import parse_formula
from ..thermo.activity import water_density, water_dielectric

SOLUTE_DENSITY_G_CM3 = 1.8  # rough mean density of dissolved solutes, used for the water estimate


def water_kg(cond: dict, reagents: list[dict], T: float) -> tuple[float, str]:
    """Mass of solvent water; explicit conditions.water_kg wins."""
    if cond.get("water_kg"):
        return float(cond["water_kg"]), "задано пользователем"
    V = float(cond.get("volume_L") or 1.0)
    rho = water_density(T)
    solute_cm3 = 0.0
    extra_water = 0.0
    for r in reagents:
        c = parse_formula(r["formula"])
        if c.key == parse_formula("H2O").key:
            extra_water += r["moles"] * 0.018015268
            continue
        if r.get("phase") == "aq":
            solute_cm3 += r["moles"] * c.molar_mass() / SOLUTE_DENSITY_G_CM3
    w = rho * max(V * 1000.0 - solute_cm3, 0.05 * V * 1000.0) / 1000.0
    return w + extra_water, (f"оценка: {V:g} л раствора минус объем растворенных веществ "
                             f"(~{solute_cm3:.0f} см3), плотность воды {rho:.4f} г/см3")


def dielectric(solvent: dict, T: float) -> float:
    return float(solvent.get("dielectric_constant") or water_dielectric(T))
