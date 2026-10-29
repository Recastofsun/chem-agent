"""Электролиз водного раствора с инертными электродами (W-15, замена однокамерного режима).

Прежний режим фиксировал потенциал компонента заряда в минимизации Гиббса и нарушал электронейтральность:
CuCl2 при 2 В давал 27 моль H2 и 54 моль OH- (невязка 3e5). Электролиз - не равновесие, а процесс,
который ток проводит через выбранные полуреакции; поэтому здесь последовательная модель:
1. Катод - восстанавливается частица с наибольшим потенциалом: ионы металлов M^z+ -> M
   (E = ΔGf(M^z+)/(zF) + RT/(zF)·ln c) или H+/H2O -> H2 (E = -0,0592·pH - η_H2).
2. Анод - окисляется частица с наименьшим потенциалом: галогенид-ионы X- -> X2 (E = -ΔGf(X-)/F + η_X2,
   F- не окисляется) или H2O/OH- -> O2 (E = 1,229 - 0,0592·pH + η_O2). Кислородсодержащие анионы не окисляются.
   Потенциалы считаются из ΔGf базы, таблица E0 не нужна.
3. Напряжение разложения U = E_анод - E_катод; приложенное меньше - электролиза нет.
4. Заряд: current_A·duration_s, иначе - до израсходования электроактивного вещества (первичный электролиз).
   Если оба электрода разлагают воду, условно 2 моль e- на моль электролита (на уравнение не влияет).
5. Новые ионы в растворе: OH- с катода связывается с катионом-зрителем (NaCl -> NaOH), H+ с анода -
   с анионом-зрителем (CuSO4 -> H2SO4); H+ и OH- с разных электродов нейтрализуются в воду.
Перенапряжения - для графита/платины при умеренной плотности тока: η_H2 = 0,4 В, η_O2 = 0,8 В, η_X2 = 0,1 В
(с ними выполняется школьное правило: галогенид окисляется раньше воды, металлы после Al восстанавливаются).
Ячейка неразделенная, но продукты электродов считаются разделенными (Cl2 + NaOH -> NaClO не учитывается).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..parser.formula import parse_formula

F = 96485.332
R = 8.314462618
ETA_H2, ETA_O2, ETA_X2 = 0.4, 0.8, 0.1
HALIDES = {"Cl": "Cl2", "Br": "Br2", "I": "I2"}


@dataclass
class Half:
    electrode: str          # cathode | anode
    species: str            # что восстанавливается / окисляется
    product: str
    product_phase: str
    E_V: float
    z: int                  # электронов на частицу species
    capacity_e: float       # сколько моль e- может пройти (inf - вода)


@dataclass
class Plan:
    cathode: Half | None
    anode: Half | None
    U_decomp_V: float | None
    n_e: float = 0.0
    products: list[tuple[str, str, float]] = field(default_factory=list)   # (формула, фаза, моль)
    consumed: dict[str, float] = field(default_factory=dict)              # ион/вода -> моль
    notes: list[str] = field(default_factory=list)
    ok: bool = False


def _ions(reagents) -> tuple[dict, dict]:
    from ..search.staged_balancer import dissociate
    cat, an = {}, {}
    for r in reagents:
        parts = dissociate(r.comp.key)  # с кислотами: HCl -> H+ + Cl-
        for key, n in parts.items():
            q = key[1]
            f = _formula(key)
            if q > 0:
                cat[f] = cat.get(f, 0.0) + n * r.moles
            elif q < 0:
                an[f] = an.get(f, 0.0) + n * r.moles
    return cat, an


def _formula(key) -> str:
    from ..search.staged_balancer import _label
    return _label(key, {})


def _pH(cat: dict, an: dict, water_kg: float) -> float:
    h, oh = cat.get("H+", 0.0) / water_kg, an.get("OH", 0.0) + an.get("OH-", 0.0)
    oh /= water_kg
    if h > oh and h > 1e-7:
        return -math.log10(h - oh)
    if oh > h and oh > 1e-7:
        return 14.0 + math.log10(oh - h)
    return 7.0


def plan(reagents, water_kg: float, T: float, voltage_V: float, db, current_A: float | None = None,
         duration_s: float | None = None) -> Plan:
    cat, an = _ions(reagents)
    pH = _pH(cat, an, water_kg)
    nf = R * T / F
    cands_c, cands_a = [], []
    for f, n in cat.items():
        c = parse_formula(f)
        els = c.as_dict
        if f == "H+" or len(els) != 1:
            continue
        metal = next(iter(els))
        ion = db.find_formula(f, "aq")
        if not ion:
            continue
        z = c.charge
        E = ion[0].dGf * 1000.0 / (z * F) + nf / z * math.log(max(n / water_kg, 1e-12))
        cands_c.append(Half("cathode", f, metal, "s", E, z, n * z))
    h_cap = cat.get("H+", 0.0)
    cands_c.append(Half("cathode", "H+" if h_cap > 0 else "H2O", "H2", "g", -0.05916 * pH - ETA_H2, 1,
                        h_cap if h_cap > 0 else math.inf))
    for f, n in an.items():
        c = parse_formula(f)
        els = c.as_dict
        if len(els) == 1 and next(iter(els)) in HALIDES and c.charge == -1:
            ion = db.find_formula(f, "aq")
            if ion:
                cands_a.append(Half("anode", f, HALIDES[next(iter(els))], "", -ion[0].dGf * 1000.0 / F + ETA_X2, 1, n))
    cands_a.append(Half("anode", "H2O", "O2", "g", 1.229 - 0.05916 * pH + ETA_O2, 1, math.inf))
    cath = max(cands_c, key=lambda h: h.E_V)
    anode = min(cands_a, key=lambda h: h.E_V)
    U = anode.E_V - cath.E_V
    p = Plan(cath, anode, U)
    p.notes.append(f"Катод: {cath.species} -> {cath.product} (E = {cath.E_V:.2f} В); анод: {anode.species} -> "
                   f"{anode.product} (E = {anode.E_V:.2f} В); pH {pH:.1f}; напряжение разложения {U:.2f} В")
    if voltage_V < U:
        p.notes.append(f"Приложено {voltage_V:g} В меньше напряжения разложения {U:.2f} В: электролиз не идет")
        return p
    if current_A and duration_s:
        n_e = current_A * duration_s / F
        p.notes.append(f"Заряд {current_A * duration_s:.4g} Кл = {n_e:.4g} моль e-")
    else:
        n_e = min(cath.capacity_e, anode.capacity_e)
        if math.isinf(n_e):
            n_e = 2.0 * sum(r.moles for r in reagents)
            p.notes.append("Оба электрода разлагают воду: условно 2 моль e- на моль электролита")
        else:
            p.notes.append("Заряд не задан: электролиз до израсходования электроактивного вещества")
    n_e = min(n_e, cath.capacity_e, anode.capacity_e)
    p.n_e, p.ok = n_e, n_e > 0
    # продукты электродов
    oh = hplus = 0.0
    if cath.product == "H2":
        p.products.append(("H2", "g", n_e / 2))
        if cath.species == "H+":
            p.consumed["H+"] = n_e
        else:
            p.consumed["H2O"] = p.consumed.get("H2O", 0.0) + n_e
            oh += n_e
    else:
        p.products.append((cath.product, "s", n_e / cath.z))
        p.consumed[cath.species] = n_e / cath.z
    if anode.product == "O2":
        p.products.append(("O2", "g", n_e / 4))
        p.consumed["H2O"] = p.consumed.get("H2O", 0.0) + n_e / 2
        hplus += n_e
    else:
        x2 = db.find_formula(anode.product)
        ph = "g" if any(s.phase == "g" for s in x2) and anode.product == "Cl2" else (
            "s" if anode.product == "I2" else "l")
        p.products.append((anode.product, ph, n_e / 2))
        p.consumed[anode.species] = n_e
    # H+ и OH- с разных электродов нейтрализуются; остаток связывается со зрителями
    w = min(oh, hplus)
    if w:
        p.consumed["H2O"] -= w
        oh, hplus = oh - w, hplus - w
    if oh > 1e-12:
        spect = max(((f, n) for f, n in cat.items() if f not in (cath.species, "H+")), key=lambda t: t[1], default=None)
        if spect:
            z = parse_formula(spect[0]).charge
            p.products.append((_combine(spect[0], "OH-"), "aq", oh / z))
    if hplus > 1e-12:
        spect = max(((f, n) for f, n in an.items() if f not in (anode.species, "OH-")), key=lambda t: t[1], default=None)
        if spect:
            z = -parse_formula(spect[0]).charge
            p.products.append((_combine("H+", spect[0]), "aq", hplus / z))
    return p


def _combine(cation: str, anion: str) -> str:
    """Нейтральная формула из пары ионов: Na+ + OH- -> NaOH, H+ + SO4-2 -> H2SO4."""
    from ..parser.naming import display_formula
    from ..parser.formula import Composition
    c, a = parse_formula(cation), parse_formula(anion)
    zc, za = c.charge, -a.charge
    g = math.gcd(zc, za)
    nc, na = za // g, zc // g
    els: dict = {}
    for comp, k in ((c, nc), (a, na)):
        for e, v in comp.elements:
            els[e] = els.get(e, 0) + v * k
    return display_formula(Composition(tuple(sorted(els.items())), 0))
