"""Kinetic rule engine (rules.yaml): redox decoupling, forbidden new species, inert reagents."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from ..parser.elements import ALKALI, ALKALINE_EARTH, NONMETALS, is_metal
from ..parser.formula import Composition, parse_formula
from ..parser.oxidation import oxidation_states
from ..utils.paths import DATA_DIR

WATER_REDUCERS = ALKALI | {"Ca", "Sr", "Ba"}
AMPHOTERIC = {"Al", "Zn", "Be", "Sn", "Pb", "Ga"}
ACTIVE_METALS = {"Mg", "Zn", "Al", "Fe", "Mn"}
STRONG_BASE_METALS = ALKALI | {"Ca", "Sr", "Ba"}


@dataclass
class Reagent:
    formula: str
    comp: Composition
    moles: float
    phase: str


@dataclass
class RuleContext:
    T: float
    aqueous: bool
    reagents: list[Reagent]
    volume_L: float
    atmosphere_species: list[Composition] = field(default_factory=list)

    def elements(self) -> set[str]:
        els = {e for r in self.reagents for e, _ in r.comp.elements}
        els |= {e for a in self.atmosphere_species for e, _ in a.elements}
        if self.aqueous:
            els |= {"H", "O"}
        return els

    def has(self, formula: str) -> bool:
        key = parse_formula(formula).key
        return any(r.comp.key == key for r in self.reagents)

    def conc(self, formula: str) -> float:
        key = parse_formula(formula).key
        n = sum(r.moles for r in self.reagents if r.comp.key == key)
        return n / self.volume_L if self.volume_L > 0 else 0.0

    # ---- classifications
    @staticmethod
    def is_acid(c: Composition) -> bool:
        els = c.as_dict
        if c.charge != 0 or "H" not in els or len(els) < 2:
            return False
        if any(is_metal(e) for e in els):
            return False
        if els.get("C") and els.get("H", 0) > 1 and "O" not in els:
            return False  # hydrocarbons
        key = tuple(sorted(els.items()))
        if key in ((("H", 3), ("N", 1)), (("H", 2), ("O", 1)), (("H", 2), ("O", 2)),
                   (("C", 2), ("H", 6), ("O", 1)), (("C", 1), ("H", 4), ("O", 1)), (("H", 4), ("N", 2))):
            return False  # NH3, H2O, H2O2, alcohols, hydrazine
        return True

    @staticmethod
    def is_strong_base(c: Composition) -> bool:
        els = c.as_dict
        metals = [e for e in els if is_metal(e)]
        if len(metals) != 1 or metals[0] not in STRONG_BASE_METALS:
            return False
        rest = {k: v for k, v in els.items() if k != metals[0]}
        return set(rest) == {"O", "H"} and rest["O"] == rest["H"] or set(rest) == {"O"}

    @staticmethod
    def is_strong_oxidant(c: Composition) -> bool:
        st = oxidation_states(c.elements, c.charge)
        els = c.as_dict
        if len(els) == 1 and next(iter(els)) in ("F", "Cl", "Br", "O") and c.charge == 0:
            return True
        if st is None:
            return False
        if st.get("Mn", 0) >= 4 or st.get("Cr", 0) >= 6 or st.get("Pb", 0) >= 4:
            return True
        if st.get("Cl", -1) >= 1 or st.get("Br", -1) >= 1:
            return True
        if "O" in st and abs(st["O"] + 1) < 1e-9:
            return True  # peroxide
        if st.get("Fe", 0) >= 6:
            return True
        return False

    @staticmethod
    def is_peroxide(c: Composition) -> bool:
        st = oxidation_states(c.elements, c.charge)
        return bool(st and "O" in st and st["O"] > -2 + 1e-9 and st["O"] < 0)

    @staticmethod
    def is_organic(c: Composition) -> bool:
        from .hypotheses import is_organic as _org
        return _org(c.as_dict)

    def metals_elemental(self) -> set[str]:
        out = set()
        for r in self.reagents:
            els = r.comp.as_dict
            if len(els) == 1 and r.comp.charge == 0:
                el = next(iter(els))
                if is_metal(el):
                    out.add(el)
        return out

    # ---- predicates
    def pred(self, name: str, arg) -> bool:
        T = self.T
        if name == "T_below":
            return T < float(arg)
        if name == "T_at_least":
            return T >= float(arg)
        if name == "reagent_absent":
            return not self.has(arg) and not any(a.key == parse_formula(arg).key for a in self.atmosphere_species)
        if name == "reagent_present":
            return self.has(arg)
        if name == "no_strong_oxidant":
            return not any(self.is_strong_oxidant(r.comp) for r in self.reagents) == bool(arg)
        if name == "strong_oxidant":
            return any(self.is_strong_oxidant(r.comp) for r in self.reagents) == bool(arg)
        if name == "acid_conc_at_least":
            return self.has(arg["acid"]) and self.conc(arg["acid"]) >= float(arg["M"])
        if name == "acid_conc_below":
            return (not self.has(arg["acid"])) or self.conc(arg["acid"]) < float(arg["M"])
        if name == "no_acid":
            return (not any(self.is_acid(r.comp) for r in self.reagents)) == bool(arg)
        if name == "acid":
            return any(self.is_acid(r.comp) for r in self.reagents) == bool(arg)
        if name == "aqueous":
            return self.aqueous == bool(arg)
        if name == "no_peroxide":
            return (not any(self.is_peroxide(r.comp) for r in self.reagents)) == bool(arg)
        if name == "organic_reagent":
            return any(self.is_organic(r.comp) for r in self.reagents) == bool(arg)
        if name == "active_metal_reagent":
            return bool(self.metals_elemental() & ACTIVE_METALS) == bool(arg)
        if name == "no_water_reducer":
            m = self.metals_elemental()
            reducer = bool(m & WATER_REDUCERS) or ("Mg" in m and T >= 340)
            base = any(self.is_strong_base(r.comp) for r in self.reagents)
            reducer = reducer or bool(m & AMPHOTERIC and base)
            # hydrides (NaH, CaH2) also reduce water
            for r in self.reagents:
                st = oxidation_states(r.comp.elements, r.comp.charge)
                if st and st.get("H", 1) < 0:
                    reducer = True
            return (not reducer) == bool(arg)
        if name in ("conc_sulfuric_hot", "no_conc_sulfuric_hot"):
            hot = self.has("H2SO4") and self.conc("H2SO4") >= 10.0 and T >= 340
            return hot if name == "conc_sulfuric_hot" else not hot
        if name == "passivating_acid":
            return ((self.has("HNO3") and self.conc("HNO3") >= 10.0) or
                    (self.has("H2SO4") and self.conc("H2SO4") >= 10.0)) == bool(arg)
        raise ValueError(f"Неизвестное условие правила: {name}")


@dataclass
class RuleOutcome:
    decouple: dict[str, list[list]] = field(default_factory=dict)  # element -> groups
    forbid_new: set = field(default_factory=set)                   # composition keys
    forbid_new_class: set = field(default_factory=set)
    inert_formulas: set = field(default_factory=set)                # composition keys
    fired: list[dict] = field(default_factory=list)


@lru_cache(maxsize=1)
def load_rules() -> list[dict]:
    data = yaml.safe_load((DATA_DIR / "rules.yaml").read_text(encoding="utf-8"))
    return data["rules"]


def evaluate(ctx: RuleContext, disabled: set[str] | None = None) -> RuleOutcome:
    out = RuleOutcome()
    disabled = disabled or set()
    for rule in load_rules():
        if rule["id"] in disabled:
            continue
        conds = rule.get("if") or {}
        if not all(ctx.pred(k, v) for k, v in conds.items()):
            continue
        then = rule["then"]
        effect = False
        if "decouple" in then:
            d = then["decouple"]
            present = any(d["element"] in dict(r.comp.elements) for r in ctx.reagents) or any(
                d["element"] in dict(a.elements) for a in ctx.atmosphere_species)
            if present:
                out.decouple[d["element"]] = d["groups"]
                effect = True
        if "forbid_new" in then:
            sys_els = ctx.elements()
            for f in then["forbid_new"]:
                c = parse_formula(str(f))
                key = c.key
                if not ctx.has(str(f)) and not any(a.key == key for a in ctx.atmosphere_species):
                    out.forbid_new.add(key)
                    if all(e in sys_els for e, _ in c.elements):
                        effect = True
        if "forbid_new_class" in then:
            out.forbid_new_class.add(then["forbid_new_class"])
            cls = then["forbid_new_class"]
            els = ctx.elements()
            if cls == "organic":
                effect = "C" in els and "H" in els
            elif cls in ("oxide_if_hydroxide", "metal_hydrides"):
                effect = any(is_metal(e) for e in els) and (cls != "metal_hydrides" or "H" in els)
            elif cls == "radicals":
                effect = False  # recorded as fired only when it actually removes a species
            else:
                effect = True
        if "inert_reagent" in then:
            for f in then["inert_reagent"]["formulas"]:
                if ctx.has(f):
                    out.inert_formulas.add(parse_formula(f).key)
                    effect = True
        if effect:
            out.fired.append({"id": rule["id"], "title": rule.get("title", ""), "why": rule.get("why", "")})
    return out


def component_of(element: str, state: float | None, groups: list[list]) -> str:
    """Pseudo-element name for element in given oxidation state under decoupling groups."""
    other_idx = None
    for i, grp in enumerate(groups):
        if "others" in grp:
            other_idx = i
        if state is not None and any(isinstance(x, (int, float)) and abs(state - x) < 1e-6 for x in grp):
            return f"{element}[{i}]"
    return f"{element}[{other_idx if other_idx is not None else len(groups)}]"


def is_nonmetal_element(el: str) -> bool:
    return el in NONMETALS
