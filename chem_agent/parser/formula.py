"""Chemical formula parser.

Supports: Cu(OH)2, K4[Fe(CN)6], CuSO4·5H2O, CuSO4*5H2O, ions in several
notations (Fe+3, Fe3+, Fe^3+, SO4-2, SO4^2-, SO4--, NH4+), unicode sub/superscripts,
phase suffixes (aq)/(s)/(l)/(g) and Russian (р-р)/(тв)/(ж)/(г).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .elements import ELEMENTS, electronegativity, mass

_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")

PHASE_ALIASES = {
    "aq": "aq", "р-р": "aq", "р": "aq", "раствор": "aq", "solution": "aq",
    "s": "s", "тв": "s", "cr": "s", "c": "s", "solid": "s", "осадок": "s",
    "l": "l", "ж": "l", "liq": "l", "liquid": "l",
    "g": "g", "г": "g", "gas": "g",
}

_TOKEN = re.compile(r"([A-Z][a-z]?)|(\d+(?:\.\d+)?)|([\(\[\{])|([\)\]\}])")


class FormulaError(ValueError):
    """Formula can not be parsed."""


@dataclass(frozen=True)
class Composition:
    elements: tuple[tuple[str, float], ...]
    charge: int = 0
    phase: str | None = None
    raw: str = ""

    @property
    def as_dict(self) -> dict[str, float]:
        return dict(self.elements)

    @property
    def key(self) -> tuple:
        """Phase-independent identity: elements + charge."""
        return (self.elements, self.charge)

    def molar_mass(self) -> float:
        return sum(mass(el) * n for el, n in self.elements)

    def hill(self) -> str:
        return hill_formula(self.as_dict, self.charge)


@dataclass
class _Frame:
    counts: dict[str, float] = field(default_factory=dict)


def _normalize(text: str) -> str:
    t = text.strip().translate(_SUB).translate(_SUP)
    t = t.replace("−", "-").replace("–", "-").replace(" ", "")
    t = t.replace("↓", "").replace("↑", "")
    return t


def _split_phase(t: str) -> tuple[str, str | None]:
    m = re.search(r"\(([^()]+)\)$", t)
    if m and m.group(1).lower() in PHASE_ALIASES:
        return t[: m.start()], PHASE_ALIASES[m.group(1).lower()]
    return t, None


def _split_charge(t: str) -> tuple[str, int]:
    if t in ("e-", "e"):
        return "", -1
    # SO4^2- / Fe^3+ / SO4^-2
    m = re.match(r"^(.*)\^(\d*)([+-])$", t) or re.match(r"^(.*)\^([+-])(\d*)$", t)
    if m:
        body = m.group(1)
        g2, g3 = m.group(2), m.group(3)
        if g2 in "+-":
            sign, num = g2, g3
        else:
            sign, num = g3, g2
        n = int(num) if num else 1
        return body, n if sign == "+" else -n
    # repeated signs: SO4--, Fe+++
    m = re.match(r"^(.*?)(\++|-+)$", t)
    if m and m.group(1) and not m.group(1)[-1].isdigit():
        n = len(m.group(2))
        return m.group(1), n if m.group(2)[0] == "+" else -n
    # CRC style with explicit number after sign: SO4-2, PO4-3, Fe+3
    m = re.match(r"^(.*[A-Za-z0-9\)\]])([+-])(\d+)$", t)
    if m:
        n = int(m.group(3))
        return m.group(1), n if m.group(2) == "+" else -n
    # bare sign after a letter/bracket: Cl-, Na+, Al(OH)4-
    m = re.match(r"^(.*?[A-Za-z\)\]])([+-])(\d*)$", t)
    if m:
        n = int(m.group(3)) if m.group(3) else 1
        return m.group(1), n if m.group(2) == "+" else -n
    # chemist style for simple ions: Fe3+, Cu2+ (body without digits)
    m = re.match(r"^([A-Z][a-z]?)(\d+)([+-])$", t)
    if m:
        n = int(m.group(2))
        return m.group(1), n if m.group(3) == "+" else -n
    # SO42- style is ambiguous -> treat trailing sign as charge 1 of full body
    m = re.match(r"^(.*\d)([+-])$", t)
    if m:
        return m.group(1), 1 if m.group(2) == "+" else -1
    return t, 0


def _parse_body(body: str) -> dict[str, float]:
    if not body:
        return {}
    stack: list[dict[str, float]] = [{}]
    pos = 0
    last: dict[str, float] | str | None = None
    while pos < len(body):
        m = _TOKEN.match(body, pos)
        if not m:
            raise FormulaError(f"Неизвестный символ в формуле '{body}' на позиции {pos}")
        el, num, op, cl = m.groups()
        pos = m.end()
        if el:
            if el not in ELEMENTS and el != "D":
                raise FormulaError(f"Неизвестный элемент '{el}' в формуле '{body}'")
            el = "H" if el == "D" else el
            stack[-1][el] = stack[-1].get(el, 0) + 1
            last = el
        elif num:
            n = float(num)
            if isinstance(last, str):
                stack[-1][last] += n - 1
            elif isinstance(last, dict):
                for k, v in last.items():
                    stack[-1][k] = stack[-1].get(k, 0) + v * (n - 1)
            else:
                raise FormulaError(f"Число без элемента в формуле '{body}'")
            last = None
        elif op:
            stack.append({})
            last = None
        elif cl:
            if len(stack) == 1:
                raise FormulaError(f"Лишняя закрывающая скобка в '{body}'")
            grp = stack.pop()
            for k, v in grp.items():
                stack[-1][k] = stack[-1].get(k, 0) + v
            last = grp
    if len(stack) != 1:
        raise FormulaError(f"Незакрытая скобка в '{body}'")
    return stack[0]


def parse_formula(text: str) -> Composition:
    """Parse formula string into Composition."""
    if not text or not text.strip():
        raise FormulaError("Пустая формула")
    t = _normalize(text)
    t, phase = _split_phase(t)
    parts = re.split(r"[·•*]", t)
    body0, charge = _split_charge(parts[0])
    total: dict[str, float] = dict(_parse_body(body0))
    for extra in parts[1:]:
        m = re.match(r"^(\d+(?:\.\d+)?)?(.*)$", extra)
        k = float(m.group(1)) if m.group(1) else 1.0
        for el, n in _parse_body(m.group(2)).items():
            total[el] = total.get(el, 0) + k * n
    if not total and charge != -1:
        raise FormulaError(f"Не удалось разобрать формулу '{text}'")
    items = []
    for el, n in sorted(total.items()):
        if abs(n - round(n)) < 1e-9:
            n = int(round(n))
        if n:
            items.append((el, n))
    return Composition(tuple(items), charge, phase, text.strip())


def hill_formula(elements: dict[str, float], charge: int = 0) -> str:
    els = dict(elements)
    order: list[str] = []
    if "C" in els:
        order.append("C")
        if "H" in els:
            order.append("H")
    order += sorted(k for k in els if k not in order)
    s = "".join(f"{e}{_fmt(els[e])}" for e in order)
    return s + charge_suffix(charge)


def conventional_formula(elements: dict[str, float], charge: int = 0) -> str:
    """Formula ordered by electronegativity (NaCl, BaSO4, CaCO3)."""
    els = dict(elements)
    special = {
        (("H", 3), ("N", 1)): "NH3", (("C", 1), ("H", 4)): "CH4",
        (("H", 4), ("N", 1)): "NH4", (("H", 2), ("O", 1)): "H2O",
    }
    key = tuple(sorted(els.items()))
    if key in special:
        return special[key] + charge_suffix(charge)
    order = sorted(els, key=lambda e: (electronegativity(e), e))
    if "H" in els and "O" in els and len(els) > 2:
        # oxoacids / hydroxides: H first for acids, OH groups for metal hydroxides
        order = sorted(els, key=lambda e: (0 if e == "H" else 1, electronegativity(e)))
    return "".join(f"{e}{_fmt(els[e])}" for e in order) + charge_suffix(charge)


def charge_suffix(charge: int) -> str:
    if charge == 0:
        return ""
    sign = "+" if charge > 0 else "-"
    return sign if abs(charge) == 1 else f"{sign}{abs(charge)}"


def _fmt(n: float) -> str:
    if abs(n - 1) < 1e-9:
        return ""
    if abs(n - round(n)) < 1e-9:
        return str(int(round(n)))
    return f"{n:g}"
