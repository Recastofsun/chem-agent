"""Hypothesis generation: which species can form, and the component/element matrix.

Every species from the local database built only from elements present in the system is a
hypothesis. Kinetic rules (rules.yaml) remove kinetically blocked ones and decouple
redox states. The Gibbs minimization then decides which hypotheses are realized.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..energy.database import Species, ThermoDB
from ..parser.formula import Composition, parse_formula
from ..parser.naming import salt_decomposition
from ..parser.elements import is_metal
from ..parser.oxidation import oxidation_states
from ..thermo.equilibrium import AQ, COND, GAS, M_W, SOLVENT
from .rules import Reagent, RuleContext, RuleOutcome, component_of
from ..parser import classifier

WATER_KEY = parse_formula("H2O").key
R_GAS = 0.082057366  # L atm / (mol K)


@dataclass
class ChemSystem:
    species: list[Species]
    kinds: list[str]
    components: list[str]
    A: np.ndarray
    b: np.ndarray
    charge_col: int | None
    water_mol: float
    aqueous: bool
    reagents: list[Reagent]
    inert: list[Reagent]
    rules: RuleOutcome
    initial: np.ndarray                 # nominal initial amounts (reagents as given)
    excluded: dict[str, int] = field(default_factory=dict)
    unknown_reagents: list[str] = field(default_factory=list)
    atm_initial: np.ndarray | None = None
    atm_keys: set = field(default_factory=set)
    notes: list[str] = field(default_factory=list)

    def index_of(self, formula: str, phase: str) -> int | None:
        key = parse_formula(formula).key
        for i, s in enumerate(self.species):
            if s.key == key and s.phase == phase:
                return i
        return None


def is_organic(sp_elements: dict) -> bool:
    """Organic = contains C-H or C-C bonds (heuristic on composition).
    Inorganic carbon: CO, CO2, carbonates, HCO3-, H2CO3, cyanides/thiocyanates/cyanates,
    carbides, and small hydrocarbons C1-C2 (CH4, C2H2, C2H4, C2H6) which are classical
    inorganic-chemistry products (from carbides, CO + H2, etc.).
    """
    if any(is_metal(e) for e in sp_elements):
        return False
    c = sp_elements.get("C", 0)
    h = sp_elements.get("H", 0)
    o = sp_elements.get("O", 0)
    if c == 0:
        return False
    # Small C1-C2 hydrocarbons: methane, acetylene, ethylene, ethane — inorganic-chemistry products.
    # Только углеводороды: CH3CN, CH3Cl, CH3NH2 - органика (W-15: ацетонитрил проходил как неорганика)
    hydrocarbon = set(sp_elements) <= {"C", "H"}
    if c == 1 and h >= 1 and o == 0 and hydrocarbon:
        return False  # CH4
    if c == 2 and h >= 2 and o == 0 and hydrocarbon:
        return False  # C2H2, C2H4, C2H6
    if c == 2 and h == 0 and o == 0:
        return False  # C2 carbides
    if c == 2 and o == 4:
        return False  # oxalate
    if c >= 2:
        return True
    if h == 0:
        return False
    if o >= 3:
        return False  # HCO3-, H2CO3
    if ("N" in sp_elements or "S" in sp_elements) and h <= 1 and o <= 1:
        return False  # HCN, HSCN, HOCN
    return True


STABLE_RADICALS = {parse_formula(f).key for f in ("NO", "NO2", "ClO2", "O2")}
AQ_LIQUIDS_OK = {parse_formula(f).key for f in ("Br2", "Hg")}


def is_radical(elements: tuple, charge: int) -> bool:
    from ..parser.elements import ELEMENTS, NOBLE_GASES
    els = dict(elements)
    if len(els) == 1 and next(iter(els)) in NOBLE_GASES:
        return False
    if any(is_metal(e) for e in els):
        return False  # d/f-metal compounds with odd electron count are ordinary (Fe(OH)3, Cu2+)
    electrons = sum(ELEMENTS[e][0] * n for e, n in els.items()) - charge
    return int(round(electrons)) % 2 == 1


def species_components(elements: tuple, charge: int, decouple: dict[str, list]) -> dict[str, float]:
    out: dict[str, float] = {}
    if decouple and charge == 0 and any(el in decouple for el, _ in elements):
        dec = salt_decomposition(elements)
        if dec:
            cb, zc, p, ab, za, q = dec
            ci, ai = parse_formula(cb), parse_formula(ab)
            sc, sa = oxidation_states(ci.elements, zc), oxidation_states(ai.elements, za)
            if sc is not None and sa is not None:
                for sub, k in ((species_components(ci.elements, zc, decouple), p),
                               (species_components(ai.elements, za, decouple), q)):
                    for name, v in sub.items():
                        if name != "Z":
                            out[name] = out.get(name, 0) + v * k
                return out
    st = None
    for el, n in elements:
        if el in decouple:
            if st is None:
                st = oxidation_states(elements, charge) or {}
            name = component_of(el, st.get(el), decouple[el])
        else:
            name = el
        out[name] = out.get(name, 0) + n
    if charge:
        out["Z"] = charge
    return out


def nominal_species_for_reagent(db_species: list[Species], comp: Composition, phase: str,
                                aqueous: bool) -> list[tuple[int, float]] | None:
    """Map a reagent (formula, phase) onto species of the system: [(index, coeff)]."""
    idx = {(s.key, s.phase): i for i, s in enumerate(db_species)}
    if (comp.key, phase) in idx:
        return [(idx[(comp.key, phase)], 1.0)]
    if phase == "aq" and aqueous:
        dec = salt_decomposition(comp.elements) if comp.charge == 0 else None
        if dec:
            cb, zc, p, ab, za, q = dec
            ci = parse_formula(cb + ("+" if zc == 1 else f"+{zc}"))
            ai = parse_formula(ab + ("-" if za == -1 else f"{za}"))
            k1, k2 = (ci.key, "aq"), (ai.key, "aq")
            if k1 in idx and k2 in idx:
                return [(idx[k1], float(p)), (idx[k2], float(q))]
    for ph in ("aq", "s", "l", "g"):
        if (comp.key, ph) in idx and (ph != "aq" or aqueous):
            return [(idx[(comp.key, ph)], 1.0)]
    return None


def build_system(db_species: list[Species], reagents: list[Reagent], *, T: float, P_bar: float,
                 aqueous: bool, water_kg: float, rules: RuleOutcome,
                 atmosphere: dict[str, float] | None = None, forbidden_products: list[str] | None = None,
                 extra_forbidden_keys: set | None = None, allowed_products: set | None = None) -> ChemSystem:
    notes: list[str] = []
    inert = [r for r in reagents if r.comp.key in rules.inert_formulas]
    active = [r for r in reagents if r.comp.key not in rules.inert_formulas]
    reagent_keys = {r.comp.key for r in active}
    # ионы, на которые диссоциирует реагент, - не новые частицы: ClO4- из HClO4 не запрещается
    # правилом no_perchlorate, CN- из KCN - правилами о цианидах (W-15)
    from .staged_balancer import dissociate
    dissociated = {k for r in active for k in dissociate(r.comp.key)} if aqueous else set()
    atm_keys = {parse_formula(f).key for f in (atmosphere or {})}
    elements: set[str] = set()
    for r in active:
        elements |= {e for e, _ in r.comp.elements}
    if aqueous:
        elements |= {"H", "O"}
    for f in (atmosphere or {}):
        elements |= {e for e, _ in parse_formula(f).elements}
    forbidden = {parse_formula(f).key for f in (forbidden_products or [])}
    forbidden |= extra_forbidden_keys or set()
    excluded: dict[str, int] = {}

    def skip(reason: str) -> bool:
        excluded[reason] = excluded.get(reason, 0) + 1
        return False

    from .rules import RuleContext
    organic_reagents = [r for r in active if RuleContext.is_organic(r.comp)]  # с солями органических кислот
    hydroxide_metals: dict[str, set] = {}
    AMMINE_METALS = ("Cu", "Zn", "Ni", "Co", "Ag", "Cd", "Hg")
    _nh3_key = parse_formula("NH3").key
    nh3_mol = sum(r.moles for r in active if r.comp.key == _nh3_key)
    ammonia_dissolves: set[str] = set()
    if nh3_mol > 0:
        for _el in AMMINE_METALS:
            _mmol = sum(n * r.moles for r in active for e, n in r.comp.elements if e == _el)
            if _mmol > 0 and nh3_mol >= 4.0 * _mmol:
                ammonia_dissolves.add(_el)
    AMPHOTERIC_METALS = ("Al", "Zn", "Be", "Sn", "Pb", "Ga", "Cr")
    _strong_base_metals = ("Na", "K")
    _oh_mol = 0.0
    for r in active:
        els = dict(r.comp.elements)
        if any(m in els for m in _strong_base_metals) and "O" in els and "H" in els \
                and els.get("O", 0) == els.get("H", 0):
            _oh_mol += r.moles * els["O"]
    alkali_dissolves: set[str] = set()
    if _oh_mol > 0:
        for _el in AMPHOTERIC_METALS:
            _mmol = sum(n * r.moles for r in active for e, n in r.comp.elements if e == _el)
            if _mmol > 0 and _oh_mol >= 4.0 * _mmol:
                alkali_dissolves.add(_el)
    if "oxide_if_hydroxide" in rules.forbid_new_class:
        for s in db_species:
            els = dict(s.elements)
            if s.phase == "s" and s.charge == 0 and set(els) - {"O", "H"} and len(set(els) - {"O", "H"}) == 1 \
                    and els.get("O") == els.get("H") and els.get("O"):
                m = next(iter(set(els) - {"O", "H"}))
                if not is_metal(m):  # Si(OH)4, B(OH)3 - оксокислоты, а не гидроксиды: SiO2 не запрещаем (W-09)
                    continue
                st = oxidation_states(s.elements, 0) or {}
                hydroxide_metals.setdefault(m, set()).add(round(st.get(m, 0), 3))

    def blocked_oxide(s: Species) -> bool:
        els = dict(s.elements)
        if s.phase != "s" or set(els) - {"O"} == set() or len(set(els) - {"O"}) != 1 or "O" not in els:
            return False
        m = next(iter(set(els) - {"O"}))
        if m not in hydroxide_metals:
            return False
        st = (oxidation_states(s.elements, 0) or {}).get(m)
        if st is None:
            return True
        if abs(st - round(st)) > 1e-6:
            return True  # mixed-valence oxide (Fe3O4, Mn3O4)
        return round(st, 3) in hydroxide_metals[m]

    def keep(s: Species) -> bool:
        if s.dGf is None:
            return skip("нет dGf")
        if not all(e in elements for e, _ in s.elements):
            return False
        els = dict(s.elements)
        present = s.key in reagent_keys or s.key in atm_keys or s.key in dissociated
        if s.key in forbidden and not present:
            return skip("запрещено пользователем")
        if aqueous:
            if s.phase == "g" and s.key == WATER_KEY:
                return skip("испарение воды не моделируется")
            if s.phase == "l" and s.key != WATER_KEY and s.key not in AQ_LIQUIDS_OK and not present:
                return skip("жидкость смешивается с водой или реагирует с ней")
        else:
            if s.phase == "aq":
                return False
        if s.key in rules.forbid_new and not present:
            return skip("кинетическое правило")
        if rules.forbid_new and not present and s.charge == 0 and s.phase in ("s", "aq") and len(els) > 1:
            # W-16: соль запрещенного иона (NaHCOO(тв) при запрете HCOO-) тоже не образуется
            parts = dissociate(s.key)
            if len(parts) > 1 and any(k in rules.forbid_new and k not in dissociated for k in parts):
                return skip("кинетическое правило (ион соли)")
        if "radicals" in rules.forbid_new_class and not present and s.key not in STABLE_RADICALS and (
                is_radical(s.elements, s.charge) or (s.phase == "g" and len(els) == 1 and sum(els.values()) == 1
                                                      and not is_metal(next(iter(els))))):
            return skip("радикал или атомарный газ")
        if "metal_hydrides" in rules.forbid_new_class and not present and "H" in els and len(els) == 2 \
                and s.charge == 0 and s.phase in ("s", "l") and any(is_metal(e) for e in els if e != "H"):
            return skip("гидрид металла в воде")
        if hydroxide_metals and not present and blocked_oxide(s):
            return skip("оксид вместо гидроксида (кинетика)")
        if ammonia_dissolves and not present and s.phase == "s":
            _els = dict(s.elements)
            if ("O" in _els and "H" in _els
                    and _els.get("O") == _els.get("H")
                    and len(set(_els) - {"O", "H"}) == 1):
                _metal = next(iter(set(_els) - {"O", "H"}))
                if _metal in ammonia_dissolves:
                    return skip("гидроксид растворяется в избытке аммиака")
        if alkali_dissolves and not present and s.phase == "s":
            _els = dict(s.elements)
            if ("O" in _els and "H" in _els
                    and _els.get("O") == _els.get("H")
                    and len(set(_els) - {"O", "H"}) == 1):
                _metal = next(iter(set(_els) - {"O", "H"}))
                if _metal in alkali_dissolves:
                    return skip("амфотерный гидроксид растворяется в избытке щёлочи")
        if rules.forbid_new_class:
            # 1. Органика (уже была)
            if "organic" in rules.forbid_new_class and is_organic(els) and not present:
                return skip("органика не образуется")
            
            # 2. Новые классы (алканы, алкины, пероксиды и т.д.)
            for cls in rules.forbid_new_class:
                if cls in ("organic", "oxide_if_hydroxide", "radicals", "metal_hydrides"):
                    continue # Пропускаем, они обрабатываются отдельно
                if not present and classifier.classify(s.comp, cls):
                    return skip(f"класс {cls} запрещен")
        if organic_reagents and is_organic(els) and not present and s.key not in (allowed_products or ()):
            # allow only conjugate acid/base forms of organic reagents
            ok = False
            for r in organic_reagents:
                re_ = r.comp.as_dict
                if all(els.get(k, 0) == re_.get(k, 0) for k in ("C", "O", "N", "S")):
                    ok = True
            if not ok:
                return skip("органика вне области применимости")
        if s.phase == "aq" and s.charge == 0 and len(els) == 1 and next(iter(els)) not in (
                "H", "O", "N", "Cl", "Br", "I", "F"):
            return False
        return True

    species = [s for s in db_species if keep(s)]
    # component matrix
    comp_rows = [species_components(s.elements, s.charge, rules.decouple) for s in species]
    reag_rows = [species_components(r.comp.elements, r.comp.charge, rules.decouple) for r in active]
    b_map: dict[str, float] = {}
    for r, row in zip(active, reag_rows):
        for k, v in row.items():
            b_map[k] = b_map.get(k, 0.0) + v * r.moles
    water_mol = water_kg / M_W if aqueous else 0.0
    if aqueous:
        wrow = species_components(WATER_KEY[0], 0, rules.decouple)
        for k, v in wrow.items():
            b_map[k] = b_map.get(k, 0.0) + v * water_mol
    if atmosphere:
        for f, n in atmosphere.items():
            c = parse_formula(f)
            for k, v in species_components(c.elements, c.charge, rules.decouple).items():
                b_map[k] = b_map.get(k, 0.0) + v * n
    b_map.setdefault("Z", 0.0)
    # drop species containing components absent from the system (b = 0, except charge)
    comps_present = {k for k, v in b_map.items() if abs(v) > 0 or k == "Z"}
    keep_idx = [i for i, row in enumerate(comp_rows)
                if all(k in comps_present and (abs(b_map[k]) > 0 or k == "Z") for k in row)]
    species = [species[i] for i in keep_idx]
    comp_rows = [comp_rows[i] for i in keep_idx]
    if not any(s.charge for s in species):
        b_map.pop("Z", None)
    components = sorted(k for k in b_map if k != "Z") + (["Z"] if "Z" in b_map else [])
    A = np.array([[row.get(c, 0.0) for c in components] for row in comp_rows], dtype=float)
    if not len(species):
        A = np.zeros((0, len(components)))
    b = np.array([b_map[c] for c in components], dtype=float)
    kinds = []
    for s in species:
        if s.phase == "aq":
            kinds.append(AQ)
        elif s.phase == "g":
            kinds.append(GAS)
        elif aqueous and s.phase == "l" and s.key == WATER_KEY:
            kinds.append(SOLVENT)
        else:
            kinds.append(COND)
    # nominal initial state
    initial = np.zeros(len(species))
    unknown: list[str] = []
    for r in active:
        m = nominal_species_for_reagent(species, r.comp, r.phase, aqueous)
        if m is None:
            unknown.append(r.formula)
            continue
        for i, k in m:
            initial[i] += k * r.moles
    if aqueous:
        wi = next((i for i, k in enumerate(kinds) if k == SOLVENT), None)
        if wi is not None:
            initial[wi] += water_mol
    atm_initial = np.zeros(len(species))
    if atmosphere:
        for f, n in atmosphere.items():
            key = parse_formula(f).key
            gi = next((i for i, s in enumerate(species) if s.key == key and s.phase == "g"), None)
            if gi is not None:
                initial[gi] += n
                atm_initial[gi] += n
    charge_col = components.index("Z") if "Z" in components else None
    return ChemSystem(species=species, kinds=kinds, components=components, A=A, b=b,
                      charge_col=charge_col, water_mol=water_mol, aqueous=aqueous, reagents=active,
                      inert=inert, rules=rules, initial=initial, excluded=excluded,
                      unknown_reagents=unknown, notes=notes, atm_initial=atm_initial, atm_keys=atm_keys)


def headspace_gas(atmosphere: dict | None, headspace_L: float, P_atm: float, T: float) -> dict[str, float]:
    """Moles of each atmospheric gas in the headspace (ideal gas)."""
    if not atmosphere or headspace_L <= 0:
        return {}
    comp = dict(atmosphere.get("composition") or {})
    total = P_atm * headspace_L / (R_GAS * T)
    s = sum(v for v in comp.values() if v)
    if 0 < s < 1.0 - 1e-6:
        # Доли - мольные доли (парциальные давления / P). Остаток - балластный газ, считаем N2.
        # Без него {"CO2": 3e-4} нормировалось в чистый CO2 под 1 атм.
        comp["N2"] = (comp.get("N2") or 0.0) + (1.0 - s)
        s = 1.0
    out = {}
    for f, x in comp.items():
        if not x or f in ("Ar", "He", "Ne"):
            continue
        out[f] = total * x / (s or 1.0)
    return out
