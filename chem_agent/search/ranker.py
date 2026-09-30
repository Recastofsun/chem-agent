"""Turn an equilibrium composition into ranked products, dissolved salts and equations."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..energy.database import Species
from ..parser.formula import Composition, parse_formula
from ..parser.naming import display_formula, russian_name
from ..thermo.equilibrium import AQ, COND, GAS, SOLVENT
from .hypotheses import WATER_KEY, ChemSystem

WEIGHTS = {"precipitate": 3.0, "gas": 3.0, "solid": 3.0, "liquid": 2.5, "dissolved_gas": 2.6,
           "molecule_aq": 2.2, "salt_solution": 2.0, "ion": 1.5, "water": 1.2}
KIND_RU = {"precipitate": "осадок", "gas": "газ", "solid": "твердое вещество", "liquid": "жидкость",
           "dissolved_gas": "растворенный газ", "molecule_aq": "молекулы в растворе",
           "salt_solution": "соль в растворе", "ion": "ион в растворе", "water": "вода"}
GAS_LIKE = {parse_formula(f).key for f in ("CO2", "H2S", "SO2", "NH3", "Cl2", "H2", "O2", "N2", "HCN",
                                           "NO", "NO2", "N2O", "Br2", "I2")}


@dataclass
class ProductEntry:
    formula: str
    phase: str
    kind: str
    moles: float
    key: tuple
    score: float = 0.0
    species_idx: list[int] = field(default_factory=list)
    parts: list[tuple[int, float]] = field(default_factory=list)  # (species index, coeff) for salts
    name_ru: str | None = None

    @property
    def mass_g(self) -> float:
        return Composition(self.key[0], self.key[1]).molar_mass() * self.moles


@dataclass
class Analysis:
    products: list[ProductEntry]
    consumed: list[tuple[int, float]]
    formed: list[tuple[int, float]]
    reaction_occurred: bool
    delta: np.ndarray
    ref_moles: float


def _salt_formula(cat: Species, an: Species) -> tuple[str, tuple, int, int]:
    from math import gcd
    zc, za = cat.charge, -an.charge
    g = gcd(zc, za)
    p, q = za // g, zc // g
    els: dict[str, float] = {}
    for e, n in cat.elements:
        els[e] = els.get(e, 0) + n * p
    for e, n in an.elements:
        els[e] = els.get(e, 0) + n * q
    comp = Composition(tuple(sorted(els.items())), 0)
    return display_formula(comp), comp.key, p, q


def hydroxo_parents(sp: list) -> dict[int, tuple[int, int]]:
    """FeOH+2 -> (index of Fe+3, 1), Fe(OH)2+ -> (Fe+3, 2): hydroxo cations as parent ion + n OH-."""
    idx = {(s.key, s.phase): i for i, s in enumerate(sp)}
    out = {}
    for i, s in enumerate(sp):
        els = dict(s.elements)
        if s.phase != "aq" or s.charge <= 0 or "O" not in els or els.get("O") != els.get("H"):
            continue
        rest = {k: v for k, v in els.items() if k not in ("O", "H")}
        if len(rest) != 1:
            continue
        nOH = int(els["O"])
        key = (tuple(sorted(rest.items())), s.charge + nOH)
        j = idx.get((key, "aq"))
        if j is not None:
            out[i] = (j, nOH)
    return out


def analyze(system: ChemSystem, n: np.ndarray, reagent_keys: set | None = None) -> Analysis:
    sp = system.species
    delta = n - system.initial
    real = [r.moles for r in system.reagents if r.moles > 1e-10]  # pH-stat placeholders are 1e-12
    ref = max(real + [1e-12])
    ref_min = min(real + [ref])
    # thresholds scale with the smallest (usually limiting) reagent: a 1e-5 mol reagent can react fully
    sig = max(1e-12, 1e-3 * ref_min)
    reagent_keys = reagent_keys or ({r.comp.key for r in system.reagents} | set(system.atm_keys))
    kinds = system.kinds
    occurred = any(abs(d) > 0.01 * ref_min for d in delta)
    # net change per substance key (dissolution of a reagent gas/solid is not a product)
    net: dict[tuple, float] = {}
    for s, d in zip(sp, delta):
        net[s.key] = net.get(s.key, 0.0) + d
    products: list[ProductEntry] = []
    if occurred:
        for i, (s, d) in enumerate(zip(sp, delta)):
            if d <= sig:
                continue
            if s.key in reagent_keys and net[s.key] <= sig:
                continue
            k = kinds[i]
            if k == SOLVENT or (s.key == WATER_KEY and not system.aqueous):
                kind = "water" if k == SOLVENT or s.phase == "l" else "gas"
            elif k == COND:
                kind = ("precipitate" if system.aqueous else "solid") if s.phase == "s" else "liquid"
            elif k == GAS:
                kind = "gas"
            elif s.charge == 0:
                kind = "dissolved_gas" if s.key in GAS_LIKE else "molecule_aq"
            else:
                kind = "ion"
            products.append(ProductEntry(s.formula, s.phase, kind, float(d), s.key,
                                         species_idx=[i], name_ru=s.name_ru))
        # dissolved salts from final major ions
        if system.aqueous:
            W = n[[i for i, k in enumerate(kinds) if k == SOLVENT]].sum() * 0.018015268
            def pairable(i):
                els = dict(sp[i].elements)
                if sp[i].formula in ("H+",):
                    return False
                if sp[i].charge > 0 and "O" in els:
                    return False  # hydroxo/oxo cations (FeOH+2, UO2+2) are not salt formers here
                return True
            major = [i for i, k in enumerate(kinds) if k == AQ and sp[i].charge != 0 and n[i] > sig
                     and pairable(i)]
            # name salts after the fully deprotonated strong-acid anion (MnSO4, not Mn(HSO4)2)
            parent = {"HSO4-": "SO4-2"}
            n = n.copy()
            for i, (j, _k) in hydroxo_parents(sp).items():
                if n[i] > sig:
                    n[j] += n[i]
                    if j not in major and sp[j].charge > 0:
                        major.append(j)
            for i in list(major):
                pf = parent.get(sp[i].formula)
                if pf:
                    j = next((k for k, x in enumerate(sp) if x.formula == pf and x.phase == "aq"), None)
                    if j is not None:
                        n[j] += n[i]
                        major.remove(i)
                        if j not in major:
                            major.append(j)
            cats = [i for i in major if sp[i].charge > 0]
            ans = [i for i in major if sp[i].charge < 0]
            Qc = sum(n[i] * sp[i].charge for i in cats)
            Qa = sum(-n[i] * sp[i].charge for i in ans)
            denom = max(Qc, Qa, 1e-300)
            for ci in cats:
                for ai in ans:
                    if sp[ci].formula == "NH4+" and sp[ai].formula == "OH-":
                        continue  # NH4+ + OH- is aqueous ammonia, not a salt
                    q_pair = n[ci] * sp[ci].charge * (-n[ai] * sp[ai].charge) / denom
                    f, key, p, q = _salt_formula(sp[ci], sp[ai])
                    moles = q_pair / (p * sp[ci].charge)
                    if moles <= sig or key in reagent_keys:
                        continue
                    products.append(ProductEntry(f, "aq", "salt_solution", float(moles), key,
                                                 species_idx=[ci, ai], parts=[(ci, p), (ai, q)],
                                                 name_ru=russian_name(Composition(key[0], 0))))
            _ = W
    # drop tiny side changes (hydrolysis, trace species) and merge the same substance in two phases
    products = [p for p in products if p.moles > 0.01 * ref_min]
    merged: dict[tuple, ProductEntry] = {}
    for p in products:
        q = merged.get(p.key)
        if q is None:
            merged[p.key] = p
            continue
        keep, other = (q, p) if WEIGHTS[q.kind] >= WEIGHTS[p.kind] else (p, q)
        if keep.parts or other.parts:
            continue
        keep.moles += other.moles
        keep.species_idx = keep.species_idx + other.species_idx
        merged[p.key] = keep
    products = list(merged.values())
    # a reagent reappearing in another phase (BaSO4 given as 'aq' precipitating) is not a product
    products = [p for p in products if p.key not in reagent_keys]
    water_change = sum(abs(d) for s, d in zip(sp, delta) if s.key == WATER_KEY)
    if system.aqueous and len(system.reagents) == 1 and water_change < 0.01 * ref_min and not any(
            p.kind in ("precipitate", "gas", "solid", "liquid", "dissolved_gas", "molecule_aq") for p in products):
        # a single electrolyte only re-speciating in water (H2SO4 -> H+ + HSO4-) is dissolution, not a reaction
        occurred = False
        products = []
    covered = {i for p in products for i, _ in p.parts}
    products = [p for p in products if not (p.kind == "ion" and p.species_idx[0] in covered)]
    for p in products:
        frac = min(1.0, p.moles / ref)
        p.score = WEIGHTS[p.kind] * (0.5 + 0.5 * frac)
    products.sort(key=lambda p: (-p.score, -p.moles, p.formula))
    if not products:
        occurred = False
    consumed = [(i, float(d)) for i, d in enumerate(delta) if d < -sig]
    formed = [(i, float(d)) for i, d in enumerate(delta) if d > sig]
    return Analysis(products, consumed, formed, occurred, delta, ref)


def top_formulas(an: Analysis, k: int = 3) -> list[tuple]:
    out: list[tuple] = []
    for p in an.products:
        if p.key not in out:
            out.append(p.key)
        if len(out) >= k:
            break
    return out
