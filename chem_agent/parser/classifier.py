"""Классификатор химических веществ для правил кинетики."""
from __future__ import annotations

from .formula import Composition
from .elements import is_metal
from .oxidation import oxidation_states


def is_peroxide(c: Composition) -> bool:
    st = oxidation_states(c.elements, c.charge)
    return bool(st and "O" in st and st["O"] > -2 + 1e-9 and st["O"] < 0)


def is_strong_oxidizer(c: Composition) -> bool:
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
        return True
    if st.get("Fe", 0) >= 3:
        return True
    if st.get("Cu", 0) >= 2:
        return True
    if st.get("Ag", 0) >= 1:
        return True
    return False


def is_carbide(c: Composition) -> bool:
    els = c.as_dict
    return "C" in els and any(is_metal(e) for e in els)


def is_alkaline_earth_carbide(c: Composition) -> bool:
    els = c.as_dict
    if not is_carbide(c):
        return False
    return any(e in ("Ca", "Sr", "Ba") for e in els)


def is_alkane(c: Composition) -> bool:
    els = c.as_dict
    if set(els.keys()) != {"C", "H"}:
        return False
    c_count = els.get("C", 0)
    h_count = els.get("H", 0)
    return h_count == 2 * c_count + 2


def is_alkene(c: Composition) -> bool:
    els = c.as_dict
    if set(els.keys()) != {"C", "H"}:
        return False
    c_count = els.get("C", 0)
    h_count = els.get("H", 0)
    return h_count == 2 * c_count


def is_alkyne(c: Composition) -> bool:
    els = c.as_dict
    if set(els.keys()) != {"C", "H"}:
        return False
    c_count = els.get("C", 0)
    h_count = els.get("H", 0)
    return h_count == 2 * c_count - 2


def is_pyrite(c: Composition) -> bool:
    els = c.as_dict
    return "Fe" in els and "S" in els and len(els) == 2 and els["S"] >= 2


def is_thiocyanate(c: Composition) -> bool:
    els = c.as_dict
    return "S" in els and "C" in els and "N" in els

def is_reducing_anion(c: Composition) -> bool:
    els = c.as_dict
    # Иодиды, бромиды, сульфиды, сульфиты, тиосульфаты
    if c.charge < 0:
        if "I" in els or "S" in els:
            return True
    return False


def is_sulfate(c: Composition) -> bool:
    els = c.as_dict
    return "S" in els and "O" in els and els.get("S", 0) == 1 and els.get("O", 0) >= 3


def classify(c: Composition, class_name: str) -> bool:
    match class_name:
        case "peroxide": return is_peroxide(c)
        case "strong_oxidizer": return is_strong_oxidizer(c)
        case "carbide": return is_carbide(c)
        case "alkaline_earth_carbide": return is_alkaline_earth_carbide(c)
        case "alkane": return is_alkane(c)
        case "alkene": return is_alkene(c)
        case "alkyne": return is_alkyne(c)
        case "pyrite": return is_pyrite(c)
        case "thiocyanate": return is_thiocyanate(c)
        case "reducing_anion": return is_reducing_anion(c)
        case "sulfate": return is_sulfate(c)
        case _: return False