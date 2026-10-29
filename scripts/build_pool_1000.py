"""Пул 1000 реакций (ТЗ 14.4): data/pool_1000.json.

Первые 100 - data/pool_100.json (ручной пул W-15). Остальные 900 генерируются систематически: семейства
учебных реакций (кислота x основание, катион x анион по таблице растворимости, ряд активности металлов,
ряд галогенов, термическое разложение, сухой синтез, электролиз, комплексы) с ожиданием по учебному правилу,
не по ядру. Уравнение подбирается здесь же (нуль-пространство матрицы элементов и заряда, дроби),
метки фаз: в воде ↓ - твердое, ↑ - газ сверх растворимости; в сухой системе метится только газ.
Две концентрации (0,01 и 0,05 моль на единицу коэффициента) там, где ожидание от нее не зависит.

Реакции, где реагента или ожидаемого продукта нет в crc.db в нужной фазе, в пул не входят (ТЗ 13.3:
пробел данных - coverage_report.json); их число печатается и пишется в data/pool_1000_excluded.json.
Запуск: python scripts/build_pool_1000.py
"""
import json
import sys
from fractions import Fraction
from math import gcd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chem_agent.energy.database import get_db  # noqa: E402
from chem_agent.parser.formula import parse_formula  # noqa: E402

OUT = ROOT / "data" / "pool_1000.json"
W = {"solvent": "water", "volume_L": 1.0}
DRY = {"solvent": "none", "volume_L": 1.0}
K = (0.01, 0.05)
# растворимость газов в 1 л воды при 298 K, моль (выше - стрелка ↑)
GAS_SOL = {"H2": 0.0, "O2": 0.0, "N2": 0.0, "CO2": 0.034, "H2S": 0.1, "Cl2": 0.09}


# ---------- формулы и уравнения

def poly(ion: str) -> bool:
    return sum(ch.isupper() for ch in ion) > 1 or any(ch.isdigit() for ch in ion)


def salt(cat: str, zc: int, an: str, za: int) -> str:
    g = gcd(zc, za)
    nc, na = za // g, zc // g
    c = (f"({cat}){nc}" if poly(cat) else f"{cat}{nc}") if nc > 1 else cat
    a = (f"({an}){na}" if poly(an) else f"{an}{na}") if na > 1 else an
    return c + a


def _vec(f: str) -> dict:
    c = parse_formula(f)
    d = dict(c.as_dict)
    d["q"] = c.charge
    return d


def balance(reac: list[str], prod: list[str]) -> list[int] | None:
    """Целые положительные коэффициенты (единственное решение) или None."""
    sp = reac + prod
    vecs = [_vec(f) for f in sp]
    rows = sorted({k for v in vecs for k in v})
    m = [[Fraction(v.get(r, 0) * (1 if j < len(reac) else -1)) for j, v in enumerate(vecs)] for r in rows]
    n = len(sp)
    piv, r = [], 0
    for col in range(n):
        p = next((i for i in range(r, len(m)) if m[i][col] != 0), None)
        if p is None:
            continue
        m[r], m[p] = m[p], m[r]
        m[r] = [x / m[r][col] for x in m[r]]
        for i in range(len(m)):
            if i != r and m[i][col] != 0:
                m[i] = [a - m[i][col] * b for a, b in zip(m[i], m[r])]
        piv.append(col)
        r += 1
    free = [c for c in range(n) if c not in piv]
    if len(free) != 1:
        return None
    x = [Fraction(0)] * n
    x[free[0]] = Fraction(1)
    for i, col in enumerate(piv):
        x[col] = -m[i][free[0]]
    if not all(v > 0 for v in x) and not all(v < 0 for v in x):
        return None
    x = [abs(v) for v in x]
    den = 1
    for v in x:
        den = den * v.denominator // gcd(den, v.denominator)
    ints = [int(v * den) for v in x]
    g = 0
    for v in ints:
        g = gcd(g, v)
    return [v // g for v in ints]


def fmt(coef: list[int], names: list[str]) -> str:
    return " + ".join((f"{k} " if k != 1 else "") + nm for k, nm in zip(coef, names))


class Gen:
    def __init__(self):
        self.db = get_db()
        self.rows, self.excluded, self.n = [], [], {}

    def has(self, f: str, ph: str) -> bool:
        if ph == "aq":
            from chem_agent.search.staged_balancer import dissociate
            c = parse_formula(f)
            keys = {s.key for s in self.db.species if s.phase == "aq"}
            parts = dissociate(c.key)
            return c.key in keys or (parts != {c.key: 1.0} and all(k in keys for k in parts))
        return bool(self.db.find_formula(f, ph))

    def add(self, cat: str, reagents: list[tuple], products: list[tuple], cond: dict, main: str,
            accept=(), base: float = 0.01, water_reac=False, water_prod=False, fixed=None, accept_eq=()):
        """reagents/products: (формула, фаза); фаза продукта задает метку. base - моль на ед. коэффициента."""
        aq = cond.get("solvent") == "water"
        rn = [f for f, _ in reagents] + (["H2O"] if water_reac else [])
        pn = [f for f, _ in products] + (["H2O"] if water_prod else [])
        coef = balance(rn, pn)
        if coef is None:
            raise ValueError(f"не уравнивается: {rn} -> {pn}")
        rc, pc = coef[:len(rn)], coef[len(rn):]
        marks = []
        for (f, ph), k in zip(products, pc):
            if ph == "g":  # на электроде газ выделяется пузырьками независимо от растворимости
                gas = k * base > GAS_SOL.get(f, 1e9) if aq and "electrolysis" not in cond else True
                marks.append(f + ("↑" if gas else ""))
            elif ph == "s" and aq:
                marks.append(f + "↓")
            else:
                marks.append(f)
        marks += ["H2O" + ("↑" if not aq and cond.get("temperature_K", 298) > 373 else "")] if water_prod else []
        eq = fmt(rc, rn) + " -> " + fmt(pc, marks)
        reag = [{"formula": f, "moles": (fixed or {}).get(f, round(k * base, 6)), "phase": ph}
                for (f, ph), k in zip(reagents, rc)]
        missing = [f"{f}({ph})" for f, ph in reagents if not self.has(f, ph)]
        missing += [f"{f}({ph})" for f, ph in products if ph in ("s", "g", "l") and not self.has(f, ph)
                    or ph == "aq" and not self.has(f, "aq")]
        self.n[cat] = self.n.get(cat, 0) + 1
        rx = {"id": f"{CAT_ID[cat]}{self.n[cat]:03d}", "category": cat, "reagents": reag, "conditions": cond,
              "expected_main": main, "accept_main": list(accept), "expected_equation": eq, "accept_equations": list(accept_eq),
              "generated": True}
        if missing:
            self.excluded.append({**rx, "missing": missing})
        else:
            self.rows.append(rx)


CAT_ID = {"нейтрализация": "N", "осаждение": "P", "ОВР": "R", "комплексы": "C", "разложение": "D",
          "электрохимия": "E", "газовые": "G"}


# ---------- семейства

ACIDS = [("HCl", "Cl", 1), ("HBr", "Br", 1), ("HI", "I", 1), ("HNO3", "NO3", 1), ("HClO4", "ClO4", 1),
         ("H2SO4", "SO4", 2), ("H3PO4", "PO4", 3)]
BASES = [("LiOH", "Li", 1), ("NaOH", "Na", 1), ("KOH", "K", 1), ("RbOH", "Rb", 1), ("CsOH", "Cs", 1),
         ("Ba(OH)2", "Ba", 2), ("Sr(OH)2", "Sr", 2), ("Ca(OH)2", "Ca", 2), ("NH3", "NH4", 1)]
# нерастворимые соли (учебная таблица растворимости при 0,01-0,05 М); None - пара пропускается (неоднозначно)
INSOL = {
    ("Ag", "Cl"): "AgCl", ("Ag", "Br"): "AgBr", ("Ag", "I"): "AgI", ("Ag", "CO3"): "Ag2CO3", ("Ag", "PO4"): "Ag3PO4",
    ("Ag", "S"): "Ag2S", ("Ag", "CrO4"): "Ag2CrO4", ("Ag", "C2O4"): "Ag2C2O4", ("Ag", "OH"): "Ag2O",
    ("Pb", "I"): "PbI2", ("Pb", "SO4"): "PbSO4", ("Pb", "CO3"): "PbCO3", ("Pb", "PO4"): "Pb3(PO4)2", ("Pb", "S"): "PbS",
    ("Pb", "CrO4"): "PbCrO4", ("Pb", "F"): "PbF2", ("Pb", "C2O4"): "PbC2O4",
    ("Ba", "SO4"): "BaSO4", ("Ba", "CO3"): "BaCO3", ("Ba", "PO4"): "Ba3(PO4)2", ("Ba", "CrO4"): "BaCrO4",
    ("Ba", "C2O4"): "BaC2O4",
    ("Ca", "CO3"): "CaCO3", ("Ca", "PO4"): "Ca3(PO4)2", ("Ca", "F"): "CaF2", ("Ca", "C2O4"): "CaC2O4",
    ("Sr", "SO4"): "SrSO4", ("Sr", "CO3"): "SrCO3", ("Sr", "PO4"): "Sr3(PO4)2", ("Sr", "F"): "SrF2",
    ("Sr", "C2O4"): "SrC2O4",
    ("Cu", "OH"): "Cu(OH)2", ("Cu", "S"): "CuS", ("Cu", "PO4"): "Cu3(PO4)2", ("Cu", "C2O4"): "CuC2O4",
    ("Zn", "OH"): "Zn(OH)2", ("Zn", "S"): "ZnS", ("Zn", "CO3"): "ZnCO3", ("Zn", "PO4"): "Zn3(PO4)2",
    ("Zn", "C2O4"): "ZnC2O4",
    ("Fe3", "OH"): "Fe(OH)3", ("Fe3", "PO4"): "FePO4",
    ("Fe", "OH"): "Fe(OH)2", ("Fe", "S"): "FeS", ("Fe", "CO3"): "FeCO3", ("Fe", "PO4"): "Fe3(PO4)2",
    ("Ni", "OH"): "Ni(OH)2", ("Ni", "S"): "NiS", ("Ni", "CO3"): "NiCO3", ("Ni", "PO4"): "Ni3(PO4)2",
    ("Co", "OH"): "Co(OH)2", ("Co", "S"): "CoS", ("Co", "CO3"): "CoCO3", ("Co", "PO4"): "Co3(PO4)2",
    ("Mn", "OH"): "Mn(OH)2", ("Mn", "S"): "MnS", ("Mn", "CO3"): "MnCO3", ("Mn", "PO4"): "Mn3(PO4)2",
    ("Mg", "OH"): "Mg(OH)2", ("Mg", "PO4"): "Mg3(PO4)2", ("Mg", "F"): "MgF2",
    ("Al", "OH"): "Al(OH)3", ("Al", "PO4"): "AlPO4",
    ("Cd", "OH"): "Cd(OH)2", ("Cd", "S"): "CdS", ("Cd", "CO3"): "CdCO3", ("Cd", "PO4"): "Cd3(PO4)2",
}
# источники катионов: (формула, катион-ключ, заряд, анион, заряд аниона)
CAT_SRC = [("AgNO3", "Ag", 1, "NO3", 1), ("Pb(NO3)2", "Pb", 2, "NO3", 1),
           ("Ba(NO3)2", "Ba", 2, "NO3", 1), ("BaCl2", "Ba", 2, "Cl", 1),
           ("Ca(NO3)2", "Ca", 2, "NO3", 1), ("CaCl2", "Ca", 2, "Cl", 1),
           ("Sr(NO3)2", "Sr", 2, "NO3", 1), ("SrCl2", "Sr", 2, "Cl", 1),
           ("Cu(NO3)2", "Cu", 2, "NO3", 1), ("CuSO4", "Cu", 2, "SO4", 2), ("CuCl2", "Cu", 2, "Cl", 1),
           ("Zn(NO3)2", "Zn", 2, "NO3", 1), ("ZnSO4", "Zn", 2, "SO4", 2), ("ZnCl2", "Zn", 2, "Cl", 1),
           ("Fe(NO3)3", "Fe3", 3, "NO3", 1), ("FeCl3", "Fe3", 3, "Cl", 1),
           ("FeSO4", "Fe", 2, "SO4", 2), ("FeCl2", "Fe", 2, "Cl", 1),
           ("Ni(NO3)2", "Ni", 2, "NO3", 1), ("NiSO4", "Ni", 2, "SO4", 2), ("NiCl2", "Ni", 2, "Cl", 1),
           ("Co(NO3)2", "Co", 2, "NO3", 1), ("CoSO4", "Co", 2, "SO4", 2), ("CoCl2", "Co", 2, "Cl", 1),
           ("MnSO4", "Mn", 2, "SO4", 2), ("MnCl2", "Mn", 2, "Cl", 1),
           ("Mg(NO3)2", "Mg", 2, "NO3", 1), ("MgSO4", "Mg", 2, "SO4", 2), ("MgCl2", "Mg", 2, "Cl", 1),
           ("Al(NO3)3", "Al", 3, "NO3", 1), ("AlCl3", "Al", 3, "Cl", 1),
           ("Cd(NO3)2", "Cd", 2, "NO3", 1), ("CdSO4", "Cd", 2, "SO4", 2), ("CdCl2", "Cd", 2, "Cl", 1)]
AN_SRC = [("NaCl", "Na", "Cl", 1), ("KCl", "K", "Cl", 1), ("NaBr", "Na", "Br", 1), ("KBr", "K", "Br", 1),
          ("NaI", "Na", "I", 1), ("KI", "K", "I", 1), ("Na2SO4", "Na", "SO4", 2), ("K2SO4", "K", "SO4", 2),
          ("Na2CO3", "Na", "CO3", 2), ("K2CO3", "K", "CO3", 2), ("Na3PO4", "Na", "PO4", 3), ("K3PO4", "K", "PO4", 3),
          ("Na2S", "Na", "S", 2), ("K2S", "K", "S", 2), ("NaOH", "Na", "OH", 1), ("KOH", "K", "OH", 1),
          ("K2CrO4", "K", "CrO4", 2), ("Na2CrO4", "Na", "CrO4", 2), ("NaF", "Na", "F", 1), ("KF", "K", "F", 1),
          ("Na2C2O4", "Na", "C2O4", 2), ("K2C2O4", "K", "C2O4", 2)]
SYM = {"Fe3": "Fe"}
# ряд активности (слева активнее); заряд иона в растворе
ACTIVITY = ["Mg", "Al", "Mn", "Zn", "Fe", "Cd", "Co", "Ni", "Sn", "Pb", "H", "Cu", "Ag"]
Z = {"Mg": 2, "Al": 3, "Mn": 2, "Zn": 2, "Fe": 2, "Cd": 2, "Co": 2, "Ni": 2, "Sn": 2, "Pb": 2, "Cu": 2, "Ag": 1}


def neutralization(g: Gen):
    for acid, an, za in ACIDS:
        for base, cat, zc in BASES:
            if (cat == "Li" and an == "PO4") or (cat in ("Rb", "Cs", "K") and an == "ClO4") \
                    or (cat == "NH4" and an == "PO4") or (cat == "Ca" and an == "SO4"):
                continue
            s = salt(cat, zc, an, za)
            insol = (cat, an) in {("Ba", "SO4"), ("Sr", "SO4"), ("Ba", "PO4"), ("Sr", "PO4"), ("Ca", "PO4")}
            acc, acc_eq = [], []
            if an == "PO4" and not insol:  # PO4(3-) гидролизуется (pKa3 12,3): при 0,01-0,05 М больше половины - HPO4(2-)
                hp = salt(cat, zc, "HPO4", 2)
                acc, acc_eq = [hp], [f"H3PO4 + 2 {base} -> {hp} + 2 H2O"]
            for k in ((0.01,) if cat == "Ca" else K):
                if base == "NH3":
                    g.add("нейтрализация", [(acid, "aq"), (base, "aq")], [(s, "aq")], W, s, base=k)
                else:
                    g.add("нейтрализация", [(acid, "aq"), (base, "aq")], [(s, "s" if insol else "aq")], W, s,
                          base=k, water_prod=True, accept=acc, accept_eq=acc_eq)


def precipitation(g: Gen):
    for csrc, ck, zc, can, zca in CAT_SRC:
        for asrc, acat, an, za in AN_SRC:
            p = INSOL.get((ck, an))
            if not p:
                continue
            spect = salt(acat, 1, can, zca)
            if ck in ("Pb", "Ba", "Sr", "Ca", "Ag") and can == "SO4":
                continue
            water = an == "OH" and ck == "Ag"
            g.add("осаждение", [(csrc, "aq"), (asrc, "aq")], [(p, "s"), (spect, "aq")], W, p, base=0.01,
                  water_prod=water)


def redox(g: Gen):
    salts = [("CuSO4", "Cu", "SO4", 2), ("Cu(NO3)2", "Cu", "NO3", 1), ("CuCl2", "Cu", "Cl", 1),
             ("AgNO3", "Ag", "NO3", 1), ("Pb(NO3)2", "Pb", "NO3", 1), ("NiSO4", "Ni", "SO4", 2),
             ("NiCl2", "Ni", "Cl", 1), ("SnCl2", "Sn", "Cl", 1), ("FeSO4", "Fe", "SO4", 2), ("CdSO4", "Cd", "SO4", 2),
             ("CoSO4", "Co", "SO4", 2), ("ZnSO4", "Zn", "SO4", 2)]
    for m in ["Mg", "Al", "Mn", "Zn", "Fe", "Cd", "Co", "Ni", "Sn", "Pb", "Cu"]:
        for sf, n, an, za in salts:
            if ACTIVITY.index(m) >= ACTIVITY.index(n):
                continue
            if m == "Al" and an != "Cl" or m == "Fe" and n == "Ag" or m == "Sn" and n == "Ag" \
                    or m == "Pb" and an in ("Cl", "SO4") or m == "Mg" and an == "NO3":
                continue
            ms = salt(m, Z[m], an, za)
            for k in K:
                g.add("ОВР", [(m, "s"), (sf, "aq")], [(n, "s"), (ms, "aq")], W, n, accept=[ms], base=k)
    for m in ["Mg", "Zn", "Fe", "Al", "Mn", "Ni", "Co", "Cd"]:
        for acid, an, za in [("HCl", "Cl", 1), ("HBr", "Br", 1), ("H2SO4", "SO4", 2)]:
            ms = salt(m, Z[m], an, za)
            for k in K:
                g.add("ОВР", [(m, "s"), (acid, "aq")], [(ms, "aq"), ("H2", "g")], W, ms, accept=["H2"], base=k)
    for m, z in [("Li", 1), ("Na", 1), ("K", 1), ("Rb", 1), ("Cs", 1), ("Ca", 2), ("Sr", 2), ("Ba", 2)]:
        h = salt(m, z, "OH", 1)
        for k in ((0.01,) if m in ("Ca", "Sr") else K):
            g.add("ОВР", [(m, "s")], [(h, "aq"), ("H2", "g")], W, h, accept=["H2"], base=k, water_reac=True)
    for x2, ph, weaker in [("Cl2", "g", ["Br", "I"]), ("Br2", "l", ["I"])]:
        for y in weaker:
            for cat, z in [("Li", 1), ("Na", 1), ("K", 1), ("Rb", 1), ("Cs", 1), ("Mg", 2), ("Ca", 2), ("Ba", 2)]:
                src = salt(cat, z, y, 1)
                prod = salt(cat, z, x2[:2] if x2 != "Cl2" else "Cl", 1)
                y2 = y + "2"
                for k in K:
                    g.add("ОВР", [(x2, ph), (src, "aq")], [(prod, "aq"), (y2, "s" if y == "I" else "aq")], W, y2,
                          accept=[prod], base=k / 2)


def complexes(g: Gen):
    # аммиакаты - в избытке аммиака (0,5 моль на 1 л): при недостатке Ni и Zn остаются низшими аммиакатами,
    # гидроксокомплексами и гидроксидами (Ni(NH3)6: lg β6 = 8,5, при 0,03 М NH3 - меньше 10%)
    for sf, an, za in [("CuSO4", "SO4", 2), ("CuCl2", "Cl", 1), ("Cu(NO3)2", "NO3", 1)]:
        for k in K:
            p = salt("Cu(NH3)4", 2, an, za)
            g.add("комплексы", [(sf, "aq"), ("NH3", "aq")], [(p, "aq")], W, p, base=k / 5, fixed={"NH3": 0.5})
    for sf, an, za in [("NiSO4", "SO4", 2), ("NiCl2", "Cl", 1), ("Ni(NO3)2", "NO3", 1)]:
        for k in K:
            p = salt("Ni(NH3)6", 2, an, za)
            g.add("комплексы", [(sf, "aq"), ("NH3", "aq")], [(p, "aq")], W, p, base=k / 5, fixed={"NH3": 0.5})
    for sf, an, za in [("ZnSO4", "SO4", 2), ("ZnCl2", "Cl", 1), ("Zn(NO3)2", "NO3", 1)]:
        for k in K:
            p = salt("Zn(NH3)4", 2, an, za)
            g.add("комплексы", [(sf, "aq"), ("NH3", "aq")], [(p, "aq")], W, p, base=k / 5, fixed={"NH3": 0.5})
    for k in K:
        g.add("комплексы", [("AgNO3", "aq"), ("NH3", "aq")], [("Ag(NH3)2NO3", "aq")], W, "Ag(NH3)2NO3", base=k / 2)
        g.add("комплексы", [("AgCl", "s"), ("NH3", "aq")], [("Ag(NH3)2Cl", "aq")], W, "Ag(NH3)2Cl", base=k / 2)
    for alk in ["Na", "K"]:
        oh = alk + "OH"
        for sf, an, za in [("ZnSO4", "SO4", 2), ("ZnCl2", "Cl", 1), ("Zn(NO3)2", "NO3", 1)]:
            p = salt(alk, 1, "Zn(OH)4", 2)
            for k in K:
                g.add("комплексы", [(sf, "aq"), (oh, "aq")], [(p, "aq"), (salt(alk, 1, an, za), "aq")], W, p,
                      base=k / 4)
        for sf, an, za in [("AlCl3", "Cl", 1), ("Al(NO3)3", "NO3", 1), ("Al2(SO4)3", "SO4", 2)]:
            p = alk + "Al(OH)4"
            for k in K:
                g.add("комплексы", [(sf, "aq"), (oh, "aq")], [(p, "aq"), (salt(alk, 1, an, za), "aq")], W, p,
                      base=k / 4)
        for k in K:
            g.add("комплексы", [("Zn(OH)2", "s"), (oh, "aq")], [(salt(alk, 1, "Zn(OH)4", 2), "aq")], W,
                  salt(alk, 1, "Zn(OH)4", 2), base=k / 2)
            g.add("комплексы", [("Al(OH)3", "s"), (oh, "aq")], [(alk + "Al(OH)4", "aq")], W, alk + "Al(OH)4",
                  base=k / 2)
        for sf, an, za in [("FeSO4", "SO4", 2), ("FeCl2", "Cl", 1)]:
            p = alk + "4Fe(CN)6"
            g.add("комплексы", [(sf, "aq"), (alk + "CN", "aq")], [(p, "aq"), (salt(alk, 1, an, za), "aq")], W, p,
                  base=0.005)


def decomposition(g: Gen):
    open_ = {"atmosphere": {"mode": "open"}}
    items = [
        ("MgCO3", ["MgO", "CO2"], 900), ("CaCO3", ["CaO", "CO2"], 1200), ("SrCO3", ["SrO", "CO2"], 1500),
        ("BaCO3", ["BaO", "CO2"], 1700), ("ZnCO3", ["ZnO", "CO2"], 700), ("CdCO3", ["CdO", "CO2"], 700),
        ("PbCO3", ["PbO", "CO2"], 700), ("MnCO3", ["MnO", "CO2"], 800), ("NiCO3", ["NiO", "CO2"], 700),
        ("Mg(OH)2", ["MgO", "H2O"], 700), ("Ca(OH)2", ["CaO", "H2O"], 900), ("Cu(OH)2", ["CuO", "H2O"], 500),
        ("Zn(OH)2", ["ZnO", "H2O"], 500), ("Fe(OH)3", ["Fe2O3", "H2O"], 600), ("Al(OH)3", ["Al2O3", "H2O"], 800),
        ("Ni(OH)2", ["NiO", "H2O"], 600), ("Cd(OH)2", ["CdO", "H2O"], 600), ("Co(OH)2", ["CoO", "H2O"], 600),
        ("Mn(OH)2", ["MnO", "H2O"], 600), ("Ba(OH)2", ["BaO", "H2O"], 1300), ("Sr(OH)2", ["SrO", "H2O"], 1100),
        ("NaHCO3", ["Na2CO3", "CO2", "H2O"], 450), ("KHCO3", ["K2CO3", "CO2", "H2O"], 500),
        ("Ag2O", ["Ag", "O2"], 700), ("HgO", ["Hg", "O2"], 800), ("KClO3", ["KCl", "O2"], 700),
        ("NaClO3", ["NaCl", "O2"], 700), ("KClO4", ["KCl", "O2"], 900),
        ("NH4Cl", ["NH3", "HCl"], 700), ("NH4Br", ["NH3", "HBr"], 750),
        ("(NH4)2CO3", ["NH3", "CO2", "H2O"], 400), ("NH4HCO3", ["NH3", "CO2", "H2O"], 400),
        ("Cu(NO3)2", ["CuO", "NO2", "O2"], 700), ("AgNO3", ["Ag", "NO2", "O2"], 800),
        ("Zn(NO3)2", ["ZnO", "NO2", "O2"], 700), ("Mg(NO3)2", ["MgO", "NO2", "O2"], 800),
        ("NaNO3", ["NaNO2", "O2"], 800), ("KNO3", ["KNO2", "O2"], 750),
        ("CuSO4·5H2O", ["CuSO4", "H2O"], 550), ("CaSO4·2H2O", ["CaSO4", "H2O"], 500),
    ]
    gases = {"CO2", "H2O", "O2", "NH3", "HCl", "HBr", "NO2", "Hg"}
    for r, prods, T in items:
        for dT in (0, 200):
            cond = {**DRY, "temperature_K": T + dT}
            if any(p in ("O2", "NO2") for p in prods):
                cond.update(open_)
            pp = [(p, "g" if p in gases else "s") for p in prods if p != "H2O"]
            g.add("разложение", [(r, "s")], pp, cond, prods[0], accept=[p for p in prods[1:] if p != "H2O"],
                  base=0.01, water_prod="H2O" in prods)


def electrolysis(g: Gen):
    for cat, z in [("Li", 1), ("Na", 1), ("K", 1), ("Cs", 1), ("Cu", 2), ("Ag", 1)]:
        for an, za in [("Cl", 1), ("Br", 1), ("I", 1), ("SO4", 2), ("NO3", 1)]:
            if cat == "Ag" and an != "NO3" or cat == "Cu" and an == "I":
                continue
            s = salt(cat, z, an, za)
            halide = an in ("Cl", "Br", "I")
            x2 = an + "2"
            x2ph = "g" if an == "Cl" else "s" if an == "I" else "aq"
            for k in (0.02, 0.1):
                for U in (4.0, 6.0):
                    cond = {**W, "electrolysis": {"enabled": True, "voltage_V": U}}
                    if cat in ("Cu", "Ag"):
                        if halide:
                            g.add("электрохимия", [(s, "aq")], [(cat, "s"), (x2, x2ph)], cond, cat, base=k)
                        else:
                            acid = salt("H", 1, an, za)
                            g.add("электрохимия", [(s, "aq")], [(cat, "s"), ("O2", "g"), (acid, "aq")], cond, cat,
                                  base=k, water_reac=True)
                    elif halide:
                        h = salt(cat, z, "OH", 1)
                        g.add("электрохимия", [(s, "aq")], [(h, "aq"), ("H2", "g"), (x2, x2ph)], cond, h,
                              accept=["H2", x2], base=k, water_reac=True)
                    else:
                        g.add_water_split(cat, s, cond, k)


def _water_split(self, cat, s, cond, k):
    # электролиз воды на фоне соли кислородной кислоты: соль - не участник уравнения
    self.n["электрохимия"] = self.n.get("электрохимия", 0) + 1
    rx = {"id": f"E{self.n['электрохимия']:03d}", "category": "электрохимия",
          "reagents": [{"formula": s, "moles": k, "phase": "aq"}], "conditions": cond, "expected_main": "H2",
          "accept_main": ["O2"], "expected_equation": "2 H2O -> 2 H2↑ + O2↑", "accept_equations": [],
          "generated": True}
    (self.rows if self.has(s, "aq") else self.excluded).append(rx)


Gen.add_water_split = _water_split


def gases(g: Gen):
    for m, ox in [("Mg", "MgO"), ("Ca", "CaO"), ("Zn", "ZnO"), ("Al", "Al2O3"), ("Fe", "Fe2O3"), ("Cu", "CuO"),
                  ("Ni", "NiO"), ("Sn", "SnO2"), ("Pb", "PbO"), ("Li", "Li2O"), ("Ba", "BaO"), ("Sr", "SrO"),
                  ("Cr", "Cr2O3"), ("Ti", "TiO2"), ("Si", "SiO2"), ("Mn", "MnO2"), ("Co", "Co3O4"), ("Cd", "CdO")]:
        for T in (700, 900):
            # MnO2 выше ~800 K отдает кислород: 4 MnO2 -> 2 Mn2O3 + O2 (Kp = 1 бар при 757 K)
            acc = (["Mn2O3"], ["4 Mn + 3 O2 -> 2 Mn2O3"]) if m == "Mn" and T > 800 else ((), ())
            g.add("газовые", [(m, "s"), ("O2", "g")], [(ox, "s")], {**DRY, "temperature_K": T}, ox, base=0.01,
                  accept=acc[0], accept_eq=acc[1])
    for T in (700, 900):
        g.add("газовые", [("C", "s"), ("O2", "g")], [("CO2", "g")], {**DRY, "temperature_K": T}, "CO2", base=0.01)
        g.add("газовые", [("S", "s"), ("O2", "g")], [("SO2", "g")], {**DRY, "temperature_K": T}, "SO2", base=0.01)
        g.add("газовые", [("H2S", "g"), ("O2", "g")], [("SO2", "g")], {**DRY, "temperature_K": T}, "SO2",
              base=0.01, water_prod=True)
        g.add("газовые", [("C2H6", "g"), ("O2", "g")], [("CO2", "g")], {**DRY, "temperature_K": T}, "CO2",
              base=0.005, water_prod=True)
        g.add("газовые", [("C3H8", "g"), ("O2", "g")], [("CO2", "g")], {**DRY, "temperature_K": T}, "CO2",
              base=0.005, water_prod=True)
    for m, z in [("Na", 1), ("K", 1), ("Li", 1), ("Mg", 2), ("Ca", 2), ("Zn", 2), ("Ba", 2), ("Ni", 2), ("Cu", 2)]:
        for x2 in ("Cl2", "Br2"):
            p = salt(m, z, x2[:2] if x2 == "Br2" else "Cl", 1)
            g.add("газовые", [(m, "s"), (x2, "g" if x2 == "Cl2" else "l")], [(p, "s")], DRY, p, base=0.01)
    g.add("газовые", [("Fe", "s"), ("Cl2", "g")], [("FeCl3", "s")], DRY, "FeCl3", base=0.005)
    for m, sul in [("Fe", "FeS"), ("Zn", "ZnS"), ("Cu", "Cu2S"), ("Pb", "PbS"), ("Mg", "MgS"), ("Ag", "Ag2S"),
                   ("Ni", "NiS"), ("Mn", "MnS"), ("Cd", "CdS"), ("Ca", "CaS")]:
        g.add("газовые", [(m, "s"), ("S", "s")], [(sul, "s")], {**DRY, "temperature_K": 700}, sul, base=0.01)
    for carb, cat, z, ph in [("Na2CO3", "Na", 1, "aq"), ("K2CO3", "K", 1, "aq"), ("CaCO3", "Ca", 2, "s"),
                             ("MgCO3", "Mg", 2, "s"), ("ZnCO3", "Zn", 2, "s"), ("BaCO3", "Ba", 2, "s"),
                             ("NaHCO3", "Na", 1, "aq"), ("KHCO3", "K", 1, "aq")]:
        for acid, an, za in [("HCl", "Cl", 1), ("HBr", "Br", 1), ("HNO3", "NO3", 1), ("HClO4", "ClO4", 1),
                             ("H2SO4", "SO4", 2)]:
            if za == 2 and cat in ("Ca", "Ba") or cat == "K" and an == "ClO4":
                continue
            s = salt(cat, z, an, za)
            g.add("газовые", [(carb, ph), (acid, "aq")], [(s, "aq"), ("CO2", "g")], W, "CO2", accept=[s], base=0.1,
                  water_prod=True)
    for sul, cat, z, ph in [("FeS", "Fe", 2, "s"), ("ZnS", "Zn", 2, "s"), ("MnS", "Mn", 2, "s"), ("Na2S", "Na", 1, "aq"),
                            ("K2S", "K", 1, "aq")]:
        for acid, an, za in [("HCl", "Cl", 1), ("HBr", "Br", 1), ("H2SO4", "SO4", 2)]:
            s = salt(cat, z, an, za)
            g.add("газовые", [(sul, ph), (acid, "aq")], [(s, "aq"), ("H2S", "g")], W, "H2S", accept=[s], base=0.3)
    for am, an, za in [("NH4Cl", "Cl", 1), ("NH4NO3", "NO3", 1), ("(NH4)2SO4", "SO4", 2), ("NH4Br", "Br", 1)]:
        for alk in ("Na", "K"):
            s = salt(alk, 1, an, za)
            for k in K:
                g.add("газовые", [(am, "aq"), (alk + "OH", "aq")], [("NH3", "aq"), (s, "aq")], W, "NH3", accept=[s],
                      base=k, water_prod=True)


def main():
    g = Gen()
    for fam in (neutralization, precipitation, redox, complexes, decomposition, electrolysis, gases):
        fam(g)
    base = json.loads((ROOT / "data" / "pool_100.json").read_text(encoding="utf-8"))
    gen = g.rows
    need = 1000 - len(base)
    by = {}
    for r in gen:
        by.setdefault(r["category"], []).append(r)
    print("сгенерировано по категориям:", {c: len(v) for c, v in by.items()}, "исключено:", len(g.excluded))
    if len(gen) < need:
        raise SystemExit(f"сгенерировано {len(gen)} < {need}")
    # пропорциональное прореживание до 900: равномерно по каждой категории
    keep, quota = [], {c: round(len(v) * need / len(gen)) for c, v in by.items()}
    diff = need - sum(quota.values())
    for c in sorted(by, key=lambda c: -len(by[c]))[:abs(diff)]:
        quota[c] += 1 if diff > 0 else -1
    for c, v in by.items():
        step = len(v) / quota[c]
        keep += [v[int(i * step)] for i in range(quota[c])]
    out = base + keep
    assert len(out) == 1000 and len({r["id"] for r in out}) == 1000
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "data" / "pool_1000_excluded.json").write_text(
        json.dumps(g.excluded, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT}: {len(out)} реакций (100 ручных + {len(keep)} сгенерированных)")


if __name__ == "__main__":
    main()
