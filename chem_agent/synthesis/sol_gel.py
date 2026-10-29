"""Золь-гель метод (W-09): параметры pH, aging_time_h (ТЗ). Тест: Si(OC2H5)4 -> SiO2.

Химия: гидролиз алкоксида M(OR)n + n H2O -> M(OH)n + n ROH и конденсация в оксидный гель (SiO2).
Термодинамику дает равновесие (TEOS + 2 H2O -> SiO2 + 4 C2H5OH, ΔG ~ -46 кДж/моль). Метод:
- разрешает спирт, отвечающий алкоксигруппе (ROH): иначе правило "новая органика только как
  сопряженная форма реагента" его запрещает;
- оценивает скорость гидролиза по pH: k = k_A·[H+] + k_B·[OH-] + k_0 (кислотный и основной катализ,
  минимум около pH 7); время гелеобразования ~ 10 периодов полугидролиза;
- тип геля: pH < 7 - полимерный (слаборазветвленные цепи, микропоры), pH > 7 - коллоидный (частицы
  Штобера, мезопоры);
- aging_time_h меньше времени гелеобразования - предупреждение: золь, гель не сформировался.
Константы - калибровка порядка величины (t1/2 ~ 100 с при pH 2, ~1000 с при pH 11, ~1 сут при pH 7),
не модель конкретного состава (соотношение вода/TEOS, растворитель, T).
"""
from __future__ import annotations

import math

from ..parser.formula import parse_formula

K_ACID = 0.69    # л/(моль с)
K_BASE = 0.69    # л/(моль с)
K_0 = 8.0e-6     # 1/с
GEL_FACTOR = 10.0
ALKOXY = {"OCH3": "CH3OH", "OC2H5": "C2H5OH", "OC3H7": "C3H7OH", "OC4H9": "C4H9OH"}

DEFAULTS = {"pH": 2.0, "aging_time_h": 24.0}


def validate(p: dict) -> dict:
    from ..parser.validator import _num
    out = {**DEFAULTS, **p}
    out["pH"] = _num(out["pH"], "method.pH", lo=0.0, hi=14.0)
    out["aging_time_h"] = _num(out["aging_time_h"], "method.aging_time_h", lo=0.0, hi=1e5)
    return out


def apply_conditions(p: dict, cond: dict) -> list[str]:
    from ..parser.validator import ValidationError
    if (cond.get("solvent") or {}).get("name") != "water":
        raise ValidationError("золь-гель метод: нужен растворитель water (гидролиз алкоксида)")
    return []


def hydrolysis_half_life_s(pH: float) -> float:
    k = K_ACID * 10.0 ** (-pH) + K_BASE * 10.0 ** (pH - 14.0) + K_0
    return math.log(2) / k


def alcohols_for(reagents) -> list[str]:
    """Спирты из алкоксигрупп реагентов: Si(OC2H5)4 -> C2H5OH."""
    out = []
    for r in reagents:
        for grp, alc in ALKOXY.items():
            if f"({grp})" in r.formula.replace(" ", "") and alc not in out:
                out.append(alc)
    return out


def analyze(p: dict, reagents, T: float, cond: dict | None = None) -> dict:
    pH, aging = p["pH"], p["aging_time_h"]
    alcohols = alcohols_for(reagents)
    t_half = hydrolysis_half_life_s(pH)
    t_gel = GEL_FACTOR * t_half
    gel = "полимерный (кислотный катализ, микропоры)" if pH < 7 else "коллоидный (основной катализ, частицы Штобера)"
    notes = []
    if not alcohols:
        notes.append("Нет алкоксидов M(OR)n среди реагентов: золь-гель гидролиз не применим, результат - "
                     "обычное равновесие")
    else:
        notes.append(f"Гидролиз алкоксида при pH {pH:g}: t1/2 ~{t_half:.2g} с, гелеобразование ~{t_gel / 3600:.2g} ч "
                     f"(оценка); гель {gel}; выделяется {', '.join(alcohols)}")
        if aging * 3600 < t_gel:
            notes.append(f"Выдержка {aging:g} ч меньше времени гелеобразования: система остается золем, показан "
                         "итог полного гидролиза и конденсации")
        else:
            notes.append(f"Выдержка {aging:g} ч: гель сформирован и состарен; оксид - аморфный (в расчете - "
                         "кристаллическая фаза из базы, аморфная менее устойчива на ~5 кДж/моль)")
    gelled = bool(alcohols) and aging * 3600 >= t_gel
    centers = sorted({e for r in reagents for e, _ in r.comp.elements if e not in ("C", "H", "O")}) if alcohols else []
    return {"method": "sol_gel", "pH": pH, "aging_time_h": aging, "hydrolysis_half_life_s": t_half,
            "gel_time_s": t_gel, "gel_type": gel if alcohols else None, "alcohols": alcohols, "gelled": gelled,
            "condensed_elements": centers if gelled else [],
            "allow_products": alcohols, "notes": notes, "initiated": False, "zone": None}


def forbidden_keys(report: dict | None, species) -> set:
    """Гель состарен: конденсация Si-OH + HO-Si -> Si-O-Si + H2O прошла, твердые гидроксиды и оксокислоты
    центрального элемента (Si(OH)4, H2SiO3) не остаются - продукт оксидная сетка. Разница ΔG
    Si(OH)4 -> SiO2 + 2 H2O по базе +2,4 кДж/моль, в пределах погрешности, кинетику конденсации
    равновесие не видит."""
    els = set((report or {}).get("condensed_elements") or [])
    out = set()
    for s in species:
        e = dict(s.elements)
        if s.phase == "s" and "H" in e and "O" in e and set(e) - {"H", "O"} and set(e) - {"H", "O"} <= els:
            out.add(s.key)
    return out


def allowed_keys(report: dict | None) -> set:
    return {parse_formula(f).key for f in (report or {}).get("allow_products") or []}
