"""User-supplied energies (highest priority)."""
from __future__ import annotations

from dataclasses import dataclass

from ..parser.formula import parse_formula
from ..parser.naming import display_formula, russian_name
from .database import Species

T0 = 298.15


@dataclass
class ManualEnergy:
    formula: str
    phase: str | None
    dGf: float | None
    dHf: float | None
    S: float | None
    Cp: float | None
    source: str
    sigma: float


def parse_manual(key: str, spec: dict, default_phase: str | None = None) -> ManualEnergy:
    comp = parse_formula(key)
    phase = spec.get("phase") or comp.phase or default_phase
    unc = spec.get("uncertainty")
    return ManualEnergy(
        formula=key, phase=phase,
        dGf=spec.get("delta_Gf_kJ_mol"), dHf=spec.get("delta_Hf_kJ_mol"),
        S=spec.get("S_J_mol_K"), Cp=spec.get("Cp_J_mol_K"),
        source=str(spec.get("source") or "user"),
        sigma=float(unc) if unc is not None else 2.0,
    )


def apply_manual(base: Species | None, m: ManualEnergy) -> tuple[Species, list[str]]:
    """Return species with manual values applied (manual always wins)."""
    warnings: list[str] = []
    comp = parse_formula(m.formula)
    if m.dGf is None:
        raise ValueError(f"Для {m.formula} в known_energies нужна delta_Gf_kJ_mol")
    dsf = None
    if m.dHf is not None:
        dsf = (m.dHf - m.dGf) / T0 * 1000.0
    elif base is not None and base.dSf is not None:
        dsf = base.dSf
        warnings.append(f"{m.formula}: задана только dGf; температурная зависимость взята из базы ({base.source})")
    src = f"user:{m.source}" if m.source not in ("user",) else "user"
    if base is not None:
        sp = base.with_energy(dGf=m.dGf, dHf=m.dHf if m.dHf is not None else base.dHf,
                              S=m.S if m.S is not None else base.S, Cp=m.Cp if m.Cp is not None else base.Cp,
                              dSf=dsf, source=src, sigma=m.sigma, note="значение пользователя")
        if base.dGf is not None and abs(base.dGf - m.dGf) > 5 * max(base.sigma, m.sigma):
            warnings.append(
                f"{m.formula} ({base.phase}): значение пользователя {m.dGf:.1f} кДж/моль отличается от базы "
                f"{base.source} ({base.dGf:.1f}) больше чем на 5 сигм - проверьте фазу и единицы")
        return sp, warnings
    phase = m.phase or "s"
    sp = Species(formula=display_formula(comp), phase=phase, elements=comp.elements, charge=comp.charge,
                 dGf=m.dGf, dHf=m.dHf, S=m.S, Cp=m.Cp, dSf=dsf, source=src, sigma=m.sigma,
                 name_ru=russian_name(comp), note="значение пользователя (частицы нет в базе)")
    if phase == "aq" and comp.charge == 0:
        warnings.append(f"{m.formula}(aq) добавлена как молекулярная частица; если это сильный электролит, "
                        "в растворе она будет диссоциировать")
    return sp, warnings
