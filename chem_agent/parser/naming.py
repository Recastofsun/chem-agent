"""Conventional formulas and Russian names for salts, oxides, molecules."""
from __future__ import annotations

from functools import lru_cache
from itertools import product

from .formula import Composition, charge_suffix, conventional_formula, parse_formula

# (formula body, charge, Russian genitive name)
CATIONS: list[tuple[str, int, str]] = [
    ("H", 1, "водорода"), ("Li", 1, "лития"), ("Na", 1, "натрия"), ("K", 1, "калия"),
    ("Rb", 1, "рубидия"), ("Cs", 1, "цезия"), ("NH4", 1, "аммония"), ("Ag", 1, "серебра"),
    ("Cu", 1, "меди(I)"), ("Tl", 1, "таллия(I)"), ("Hg2", 2, "ртути(I)"),
    ("Be", 2, "бериллия"), ("Mg", 2, "магния"), ("Ca", 2, "кальция"), ("Sr", 2, "стронция"),
    ("Ba", 2, "бария"), ("Ra", 2, "радия"), ("Zn", 2, "цинка"), ("Cd", 2, "кадмия"),
    ("Hg", 2, "ртути(II)"), ("Cu", 2, "меди(II)"), ("Fe", 2, "железа(II)"),
    ("Fe", 3, "железа(III)"), ("Co", 2, "кобальта(II)"), ("Co", 3, "кобальта(III)"),
    ("Ni", 2, "никеля(II)"), ("Mn", 2, "марганца(II)"), ("Mn", 3, "марганца(III)"),
    ("Mn", 4, "марганца(IV)"), ("Cr", 2, "хрома(II)"), ("Cr", 3, "хрома(III)"),
    ("Pb", 2, "свинца(II)"), ("Pb", 4, "свинца(IV)"), ("Sn", 2, "олова(II)"),
    ("Sn", 4, "олова(IV)"), ("Al", 3, "алюминия"), ("Ga", 3, "галлия"), ("In", 3, "индия"),
    ("Bi", 3, "висмута(III)"), ("Sb", 3, "сурьмы(III)"), ("Ti", 4, "титана(IV)"),
    ("Si", 4, "кремния(IV)"), ("V", 5, "ванадия(V)"), ("La", 3, "лантана"),
    ("Ce", 3, "церия(III)"), ("Ce", 4, "церия(IV)"), ("Sc", 3, "скандия"), ("Y", 3, "иттрия"),
    ("Zr", 4, "циркония"), ("Th", 4, "тория"), ("U", 4, "урана(IV)"), ("Au", 3, "золота(III)"),
    ("Pt", 2, "платины(II)"), ("Pd", 2, "палладия(II)"), ("Mo", 6, "молибдена(VI)"),
    ("W", 6, "вольфрама(VI)"), ("Cu(NH3)4", 2, "тетраамминмеди(II)"),
    ("Ag(NH3)2", 1, "диамминсеребра(I)"), ("Zn(NH3)4", 2, "тетраамминцинка"),
    ("Ni(NH3)6", 2, "гексаамминникеля(II)"), ("S", 4, "серы(IV)"), ("S", 6, "серы(VI)"),
    ("N", 2, "азота(II)"), ("N", 4, "азота(IV)"), ("N", 1, "азота(I)"), ("C", 2, "углерода(II)"),
    ("C", 4, "углерода(IV)"), ("P", 5, "фосфора(V)"), ("Cl", 7, "хлора(VII)"),
]

# (formula body, charge, Russian nominative name of anion)
ANIONS: list[tuple[str, int, str]] = [
    ("OH", -1, "гидроксид"), ("F", -1, "фторид"), ("Cl", -1, "хлорид"), ("Br", -1, "бромид"),
    ("I", -1, "иодид"), ("NO3", -1, "нитрат"), ("NO2", -1, "нитрит"), ("HCO3", -1, "гидрокарбонат"),
    ("HSO4", -1, "гидросульфат"), ("HSO3", -1, "гидросульфит"), ("H2PO4", -1, "дигидрофосфат"),
    ("CH3COO", -1, "ацетат"), ("HCOO", -1, "формиат"), ("MnO4", -1, "перманганат"),
    ("ClO", -1, "гипохлорит"), ("ClO2", -1, "хлорит"), ("ClO3", -1, "хлорат"),
    ("ClO4", -1, "перхлорат"), ("BrO3", -1, "бромат"), ("IO3", -1, "иодат"), ("IO4", -1, "периодат"),
    ("CN", -1, "цианид"), ("SCN", -1, "тиоцианат"), ("OCN", -1, "цианат"), ("HS", -1, "гидросульфид"),
    ("AlO2", -1, "метаалюминат"), ("Al(OH)4", -1, "тетрагидроксоалюминат"), ("BO2", -1, "метаборат"),
    ("VO3", -1, "метаванадат"), ("N3", -1, "азид"), ("H", -1, "гидрид"), ("HF2", -1, "гидродифторид"),
    ("BF4", -1, "тетрафтороборат"), ("AsO2", -1, "арсенит"), ("I3", -1, "трииодид"),
    ("O", -2, "оксид"), ("O2", -2, "пероксид"), ("S", -2, "сульфид"), ("Se", -2, "селенид"),
    ("SO4", -2, "сульфат"), ("SO3", -2, "сульфит"), ("CO3", -2, "карбонат"),
    ("HPO4", -2, "гидрофосфат"), ("CrO4", -2, "хромат"), ("Cr2O7", -2, "дихромат"),
    ("MnO4", -2, "манганат"), ("C2O4", -2, "оксалат"), ("S2O3", -2, "тиосульфат"),
    ("S2O8", -2, "пероксодисульфат"), ("SiO3", -2, "силикат"), ("MoO4", -2, "молибдат"),
    ("WO4", -2, "вольфрамат"), ("SeO4", -2, "селенат"), ("SeO3", -2, "селенит"),
    ("Zn(OH)4", -2, "тетрагидроксоцинкат"), ("B4O7", -2, "тетраборат"), ("S2", -2, "дисульфид"),
    ("C2", -2, "карбид"), ("SiF6", -2, "гексафторосиликат"),
    ("PO4", -3, "фосфат"), ("AsO4", -3, "арсенат"), ("N", -3, "нитрид"), ("P", -3, "фосфид"),
    ("VO4", -3, "ортованадат"), ("Fe(CN)6", -3, "гексацианоферрат(III)"),
    ("Fe(CN)6", -4, "гексацианоферрат(II)"), ("P2O7", -4, "дифосфат"), ("SiO4", -4, "ортосиликат"),
    ("C", -4, "карбид"),
]

MOLECULE_NAMES: dict[str, str] = {
    "H2O": "вода", "H2O2": "пероксид водорода", "H2": "водород", "O2": "кислород",
    "O3": "озон", "N2": "азот", "Cl2": "хлор", "Br2": "бром", "I2": "иод", "F2": "фтор",
    "CO2": "углекислый газ", "CO": "угарный газ", "SO2": "сернистый газ", "SO3": "оксид серы(VI)",
    "NO": "оксид азота(II)", "NO2": "оксид азота(IV)", "N2O": "оксид азота(I)",
    "N2O4": "тетраоксид диазота", "NH3": "аммиак", "H2S": "сероводород", "HCl": "хлороводород",
    "HBr": "бромоводород", "HI": "иодоводород", "HF": "фтороводород", "HCN": "циановодород",
    "CH4": "метан", "C2H6": "этан", "C2H4": "этилен", "C2H2": "ацетилен",
    "CH3COOH": "уксусная кислота", "C2H5OH": "этанол", "CH3OH": "метанол",
    "H2SO4": "серная кислота", "HNO3": "азотная кислота", "HNO2": "азотистая кислота",
    "H3PO4": "фосфорная кислота", "H2CO3": "угольная кислота", "H2SO3": "сернистая кислота",
    "HClO": "хлорноватистая кислота", "HClO4": "хлорная кислота", "H3BO3": "борная кислота",
    "HCOOH": "муравьиная кислота", "C6H12O6": "глюкоза", "C": "углерод (графит)", "S": "сера",
    "P": "фосфор", "SiO2": "оксид кремния(IV)", "P4O10": "оксид фосфора(V)",
}

METAL_NAMES: dict[str, str] = {
    "Li": "литий", "Na": "натрий", "K": "калий", "Rb": "рубидий", "Cs": "цезий", "Be": "бериллий",
    "Mg": "магний", "Ca": "кальций", "Sr": "стронций", "Ba": "барий", "Al": "алюминий",
    "Zn": "цинк", "Fe": "железо", "Cu": "медь", "Ag": "серебро", "Au": "золото", "Pt": "платина",
    "Pb": "свинец", "Sn": "олово", "Hg": "ртуть", "Ni": "никель", "Co": "кобальт",
    "Mn": "марганец", "Cr": "хром", "Ti": "титан", "Cd": "кадмий", "Si": "кремний",
    "Bi": "висмут", "Sb": "сурьма", "W": "вольфрам", "Mo": "молибден", "V": "ванадий",
}

ION_NAMES_RU: dict[tuple[str, int], str] = {}
for _b, _z, _n in CATIONS:
    ION_NAMES_RU[(_b, _z)] = "ион " + _n
for _b, _z, _n in ANIONS:
    ION_NAMES_RU.setdefault((_b, _z), _n + "-ион")


@lru_cache(maxsize=None)
def _ion_comp(body: str) -> tuple[tuple[str, float], ...]:
    return parse_formula(body).elements


def _sub(a: dict, b: dict, k: int) -> dict | None:
    out = dict(a)
    for e, n in b.items():
        out[e] = out.get(e, 0) - n * k
        if out[e] < -1e-9:
            return None
        if abs(out[e]) < 1e-9:
            del out[e]
    return out


def _group(body: str, n: int) -> str:
    if n == 1:
        return body
    simple = sum(1 for c in body if c.isupper()) == 1 and not any(ch.isdigit() for ch in body)
    return f"{body}{n}" if simple else f"({body}){n}"


@lru_cache(maxsize=4096)
def salt_decomposition(elements: tuple[tuple[str, float], ...]) -> tuple | None:
    """Find (cation_body, zc, p, anion_body, za, q) such that composition = p*cat + q*an."""
    comp = dict(elements)
    best = None
    for (cb, zc, _), (ab, za, _) in product(CATIONS, ANIONS):
        cc, ac = dict(_ion_comp(cb)), dict(_ion_comp(ab))
        # stoichiometry by charge balance
        from math import gcd
        g = gcd(zc, -za)
        p, q = -za // g, zc // g
        for mult in (1, 2, 3):
            rest = _sub(comp, cc, p * mult)
            if rest is None:
                break
            rest = _sub(rest, ac, q * mult)
            if rest is not None and not rest:
                score = (len(ab) + len(cb), p + q)
                cand = (cb, zc, p * mult, ab, za, q * mult)
                if best is None or score < best[0]:
                    best = (score, cand)
                break
    return None if best is None else best[1]


# простые органические молекулы: полуструктурная запись вместо брутто (H6C2O -> C2H5OH)
ORGANIC_DISPLAY = {
    (("C", 2), ("H", 6), ("O", 1)): "C2H5OH", (("C", 1), ("H", 4), ("O", 1)): "CH3OH",
    (("C", 2), ("H", 4), ("O", 2)): "CH3COOH", (("C", 3), ("H", 8), ("O", 1)): "C3H7OH",
    (("C", 4), ("H", 10), ("O", 1)): "C4H9OH",
}


def display_formula(comp: Composition, hydrate_n: int = 0) -> str:
    els = comp.as_dict
    if hydrate_n:
        els = _sub(els, {"H": 2, "O": 1}, hydrate_n) or els
    base = None
    if comp.charge == 0:
        key = tuple(sorted(els.items()))
        conv = conventional_formula(els)
        org = ORGANIC_DISPLAY.get(tuple(sorted((e, int(n)) for e, n in els.items())))
        if org:
            base = org
        elif conv in MOLECULE_NAMES or len(els) == 1:
            base = conv
        else:
            dec = salt_decomposition(key)
            if dec:
                cb, _, p, ab, _, q = dec
                if cb == "H" and ab not in ("O", "O2"):
                    base = _group(cb, p) + _group(ab, q)
                elif ab == "OH" and cb not in ("H",):
                    base = _group(cb, p) + ("OH" if q == 1 else f"(OH){q}")
                else:
                    base = _group(cb, p) + _group(ab, q)
        if base is None:
            base = conv
    else:
        base = None
        for b, z, _ in CATIONS + ANIONS:
            if z == comp.charge and dict(_ion_comp(b)) == els:
                base = b + charge_suffix(z)
                break
        if base is None:
            base = conventional_formula(els, comp.charge)
    if hydrate_n:
        base += f"·{hydrate_n}H2O" if hydrate_n > 1 else "·H2O"
    return base


def russian_name(comp: Composition) -> str | None:
    els = comp.as_dict
    conv = conventional_formula(els, comp.charge)
    if comp.charge == 0:
        if conv in MOLECULE_NAMES:
            return MOLECULE_NAMES[conv]
        if len(els) == 1:
            el = next(iter(els))
            if el in METAL_NAMES:
                return METAL_NAMES[el]
        dec = salt_decomposition(tuple(sorted(els.items())))
        if dec:
            cb, zc, _, ab, za, _ = dec
            cname = next((n for b, z, n in CATIONS if b == cb and z == zc), None)
            aname = next((n for b, z, n in ANIONS if b == ab and z == za), None)
            if cb == "H" and aname:
                return None
            if cname and aname:
                return f"{aname} {cname}"
        return None
    for b, z, _ in CATIONS + ANIONS:
        if z == comp.charge and dict(_ion_comp(b)) == els:
            return ION_NAMES_RU.get((b, z))
    return None


HYDRATE_WORDS = {
    "monohydrate": 1, "hemihydrate": 0, "dihydrate": 2, "trihydrate": 3, "tetrahydrate": 4,
    "pentahydrate": 5, "hexahydrate": 6, "heptahydrate": 7, "octahydrate": 8,
    "nonahydrate": 9, "decahydrate": 10, "dodecahydrate": 12,
}


def hydrate_count(name_en: str) -> int:
    low = (name_en or "").lower()
    for w, n in sorted(HYDRATE_WORDS.items(), key=lambda kv: -len(kv[0])):
        if w in low:
            return n
    return 0
