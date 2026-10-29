"""Heuristic oxidation-state assignment (used for redox decoupling rules)."""
from __future__ import annotations

from functools import lru_cache

from .elements import ALKALI, ALKALINE_EARTH, electronegativity, is_metal

# common negative states for the most electronegative partner in binary compounds
_NEG = {"F": -1, "Cl": -1, "Br": -1, "I": -1, "O": -2, "S": -2, "Se": -2, "Te": -2,
        "N": -3, "P": -3, "As": -3, "C": -4, "H": -1, "Si": -4, "B": -3}


@lru_cache(maxsize=8192)
def oxidation_states(elements: tuple[tuple[str, float], ...], charge: int = 0) -> dict[str, float] | None:
    """Return {element: oxidation state} or None if ambiguous.

    Average states are returned for mixed-valence species (Fe3O4 -> Fe 8/3).
    """
    els = dict(elements)
    if len(els) == 1:
        (el, n), = els.items()
        return {el: charge / n}
    fixed: dict[str, float] = {}
    only_metals_besides_h = all(is_metal(e) for e in els if e != "H")
    for e in els:
        if e == "F":
            fixed[e] = -1
        elif e in ALKALI:
            fixed[e] = 1
        elif e in ALKALINE_EARTH:
            fixed[e] = 2
        elif e == "Al":
            fixed[e] = 3
        elif e == "H":
            fixed[e] = -1 if only_metals_besides_h else 1
        elif e == "O":
            fixed[e] = -2
    # цианид-лиганд CN-: C +2, N -3 (K4[Fe(CN)6], Fe(CN)6-3, Ag(CN)2-; W-15). Иначе у комплекса два
    # неизвестных (металл и C/N) и разбор не удавался
    if "C" in els and "N" in els and els["C"] == els["N"] and not set(els) & {"O", "S"}:
        fixed.setdefault("C", 2)
        fixed.setdefault("N", -3)
    unknown = [e for e in els if e not in fixed]

    def solve(fx: dict[str, float], unk: list[str]) -> dict[str, float] | None:
        rest = charge - sum(fx[e] * els[e] for e in fx)
        if len(unk) == 1:
            return {**fx, unk[0]: rest / els[unk[0]]}
        if not unk:
            return fx if abs(rest) < 1e-9 else None
        return None

    if len(unk := unknown) <= 1:
        res = solve(fixed, unk)
        if res is not None:
            return res
        # peroxides / superoxides / hydrides: release O, then H
        for release in ("O", "H"):
            if release in fixed:
                fx = {k: v for k, v in fixed.items() if k != release}
                res = solve(fx, [release] + unknown) if not unknown else None
                if res is not None:
                    return res
        return None
    if charge == 0:
        from .naming import salt_decomposition
        from .formula import parse_formula
        dec = salt_decomposition(elements)
        if dec:
            cb, zc, _p, ab, za, _q = dec
            ci, ai = parse_formula(cb), parse_formula(ab)
            sc = oxidation_states(ci.elements, zc)
            sa = oxidation_states(ai.elements, za)
            if sc is not None and sa is not None:
                merged = dict(sa)
                for k, v in sc.items():
                    if k in merged and abs(merged[k] - v) > 1e-9:
                        break
                    merged[k] = v
                else:
                    return merged
    if len(unk) == 2:
        hal = [e for e in unk if e in ("Cl", "Br", "I")]
        if len(hal) == 1:
            fx = dict(fixed)
            fx[hal[0]] = -1
            other = [e for e in unk if e != hal[0]][0]
            res = solve(fx, [other])
            if res is not None and -4 <= res[other] <= 8:
                return res
        a, b = sorted(unk, key=electronegativity)  # a less electronegative
        if b in _NEG:
            fx = dict(fixed)
            fx[b] = _NEG[b]
            res = solve(fx, [a])
            if res is not None and 0 <= res[a] <= 8:
                return res
    return None


def state_of(elements: tuple[tuple[str, float], ...], charge: int, element: str) -> float | None:
    st = oxidation_states(elements, charge)
    if st is None:
        return None
    return st.get(element)
