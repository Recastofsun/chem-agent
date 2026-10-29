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

NOT_COMPLEX_FORMERS = {"Li", "Na", "K", "Rb", "Cs", "Be", "Mg", "Ca", "Sr", "Ba"}


def is_cyanide_complex(c: Composition) -> bool:
    """Цианидный комплекс металла: K3[Fe(CN)6], K4[Fe(CN)6], Fe(CN)6-3, Ag(CN)2-.
    KCN, NaCN, HCN - нет: их гидролиз и протонирование идут свободно."""
    els = c.as_dict
    if not ("C" in els and "N" in els and els["C"] == els["N"]) or set(els) & {"O", "S", "H"}:
        return False
    return any(is_metal(e) and e not in NOT_COMPLEX_FORMERS for e in els)


def is_carbon_fragment(c: Composition) -> bool:
    """Неорганическая частица углерода не в степени +4: CH4, CO, оксалаты, карбиды, цианиды.
    То, во что распадается углеродный скелет органики. CO2 и карбонаты - нет."""
    from ..search.hypotheses import is_organic
    els = c.as_dict
    if "C" not in els or is_organic(els):
        return False
    st = oxidation_states(c.elements, c.charge)
    return bool(st) and "C" in st and abs(st["C"] - 4) > 1e-9


def is_aluminosilicate(c: Composition) -> bool:
    """Алюмосиликат: Al, Si и O в одной частице (каолинит, цеолиты, полевые шпаты)."""
    els = c.as_dict
    return {"Al", "Si", "O"} <= set(els)


def is_cyanide(c: Composition) -> bool:
    """Цианид: группа C≡N без O и S - KCN, HCN, CN-, K4[Fe(CN)6]. Не цианат, не тиоцианат."""
    els = c.as_dict
    return "C" in els and "N" in els and els["C"] == els["N"] and not set(els) & {"O", "S"}         and els.get("H", 0) <= els["C"]


def is_perchlorate(c: Composition) -> bool:
    """Хлор(VII): ClO4-, HClO4, перхлораты металлов, Cl2O7."""
    st = oxidation_states(c.elements, c.charge)
    return bool(st) and abs(st.get("Cl", 0) - 7) < 1e-9


INERT_GASES = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}


def is_inert(c: Composition) -> bool:
    """Кинетически инертные простые вещества: N2 (тройная связь) и благородные газы."""
    els = c.as_dict
    if c.charge or len(els) != 1:
        return False
    el, n = next(iter(els.items()))
    return el in INERT_GASES and n == 1 or el == "N" and n == 2


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
        case "perchlorate": return is_perchlorate(c)
        case "cyanide_complex": return is_cyanide_complex(c)
        case "carbon_fragment": return is_carbon_fragment(c)
        case "aluminosilicate": return is_aluminosilicate(c)
        case "cyanide": return is_cyanide(c)
        case "free_cyanide": return is_cyanide(c) and not is_cyanide_complex(c)  # KCN, HCN, CN-
        case "inert": return is_inert(c)
        case _: return False