"""Russian number formatting: decimal comma, thin groups by space, scientific for extremes."""
from __future__ import annotations

import math
import re


def num(v, digits: int = 4) -> str:
    if v is None:
        return "неизвестно"
    if isinstance(v, bool):
        return "да" if v else "нет"
    if not isinstance(v, (int, float)) or (isinstance(v, float) and not math.isfinite(v)):
        return str(v)
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e6 or a < 1e-3:
        m, e = f"{v:.{max(1, digits - 1)}e}".split("e")
        return f"{m.replace('.', ',')}·10^{int(e)}"
    if a >= 1000:
        s = f"{v:,.1f}" if a < 1e5 else f"{v:,.0f}"
        return s.replace(",", " ").replace(".", ",")
    s = f"{v:.{digits}g}"
    return s.replace(".", ",")


def pm(v, s, digits: int = 4) -> str:
    if v is None:
        return "неизвестно"
    if s is None:
        return num(v, digits)
    return f"{num(v, digits)} ± {num(s, 2)}"


def pct(v) -> str:
    return "неизвестно" if v is None else f"{v * 100:.0f} %"


_SUB_MAP = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUP_MAP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
_CHEM_AFTER = "[A-Za-z\\)\\]₀-₉]"


def chem(s):
    """Render a chemical formula with Unicode subscripts and superscript charges.
    Cu(NH3)4SO4 -> Cu(NH₃)₄SO₄ ;  Fe+3 -> Fe³⁺ ;  H2O -> H₂O.
    Coefficients ('2 NaOH') and arrows ('->') are left untouched."""
    if not s:
        return s
    s = re.sub(r"(?<=" + _CHEM_AFTER + r")(\d+)",
               lambda m: m.group(1).translate(_SUB_MAP), s)
    s = re.sub(r"(?<=" + _CHEM_AFTER + r")([+\-])(?!>)(\d*)",
               lambda m: (m.group(2).translate(_SUP_MAP) if m.group(2) else "")
                         + m.group(1).translate(_SUP_MAP), s)
    return s