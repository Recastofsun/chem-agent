"""Фотохимический метод (W-05): параметры wavelength_nm, intensity_W (ТЗ: "intensity").

Модель - фотоинициирование. Квант с энергией E = hc/λ разрывает связь поглощающего реагента
(Cl2 -> 2 Cl·), дальше идет темновая цепь. Свет снимает кинетический запрет "газовая смесь без
инициатора" (правило gas_mix_no_igniter), если λ не длиннее порога фотолиза хотя бы одного реагента.
Порог = min(hc/D0, длинноволновая граница поглощения). Термодинамику свет не меняет: эндергоничный
фотолиз (AgBr -> Ag + Br2) равновесная модель не воспроизводит, это выдается предупреждением.

Поток фотонов q = P·λ/(h·c·N_A) моль/с, время превращения t = n / (q·Φ) - оценка снизу по времени
(весь свет поглощен).
"""
from __future__ import annotations

from ..parser.formula import parse_formula

H_PLANCK = 6.62607015e-34
C_LIGHT = 2.99792458e8
N_A = 6.02214076e23
KJ_NM = H_PLANCK * C_LIGHT * N_A * 1e9 / 1e3  # E (кДж/моль) = KJ_NM / λ (нм), 119 627

# формула: (порог λ, нм; процесс; чем ограничен порог). D0 - CRC Handbook (энергии связей при 298 K),
# границы поглощения и ширины запрещенной зоны галогенидов серебра - оценка, не сверена построчно.
PHOTOLYSIS = {
    "Cl2": (493, "Cl2 -> 2 Cl·", "D0 242,6 кДж/моль"),
    "Br2": (620, "Br2 -> 2 Br·", "D0 192,8 кДж/моль"),
    "I2": (795, "I2 -> 2 I·", "D0 151,1 кДж/моль"),
    "F2": (400, "F2 -> 2 F·", "граница поглощения (D0 158,7 кДж/моль дает 754 нм)"),
    "O2": (242, "O2 -> 2 O", "D0 498,4 кДж/моль"),
    "O3": (850, "O3 -> O2 + O", "граница полосы Шаппюи"),
    "H2O2": (360, "H2O2 -> 2 OH·", "граница поглощения (D0 O-O 213 кДж/моль)"),
    "NO2": (398, "NO2 -> NO + O", "D0 ON-O 300 кДж/моль"),
    "HI": (330, "HI -> H· + I·", "граница поглощения (D0 298 кДж/моль)"),
    "AgCl": (381, "AgCl -> Ag + 1/2 Cl2", "ширина запрещенной зоны 3,25 эВ"),
    "AgBr": (463, "AgBr -> Ag + 1/2 Br2", "ширина запрещенной зоны 2,68 эВ"),
    "AgI": (443, "AgI -> Ag + 1/2 I2", "ширина запрещенной зоны 2,80 эВ"),
}
_KEYS = {parse_formula(f).key: f for f in PHOTOLYSIS}

# квантовый выход цепных реакций (порядок величины): H2 + Cl2 - 10^4...10^6 (Боденштейн, Нернст)
CHAIN_YIELD = {frozenset(("H2", "Cl2")): 1e5}

DEFAULTS = {"wavelength_nm": None, "intensity_W": 1.0, "quantum_yield": None, "duration_s": None}


def validate(p: dict) -> dict:
    from ..parser.validator import ValidationError, _num
    out = {**DEFAULTS, **p}
    if "intensity" in p and "intensity_W" not in p:
        out["intensity_W"] = p["intensity"]
    out.pop("intensity", None)
    if out["wavelength_nm"] is None:
        raise ValidationError("method.wavelength_nm: обязательный параметр фотохимического метода")
    out["wavelength_nm"] = _num(out["wavelength_nm"], "method.wavelength_nm", lo=100.0, hi=3000.0)
    out["intensity_W"] = _num(out["intensity_W"], "method.intensity_W", lo=0.0, hi=1e5)
    out["quantum_yield"] = _num(out["quantum_yield"], "method.quantum_yield", lo=1e-9, hi=1e9, allow_none=True)
    out["duration_s"] = _num(out["duration_s"], "method.duration_s", lo=0.0, allow_none=True)
    return out


def photon_energy_kJ(wavelength_nm: float) -> float:
    return KJ_NM / wavelength_nm


def photon_flux_mol_s(power_W: float, wavelength_nm: float) -> float:
    return power_W * wavelength_nm * 1e-9 / (H_PLANCK * C_LIGHT * N_A)


def analyze(p: dict, reagents, T: float, cond: dict | None = None) -> dict:
    lam, P = p["wavelength_nm"], p["intensity_W"]
    absorbers, below = [], []
    for r in reagents:
        f = _KEYS.get(r.comp.key)
        if f is None:
            continue
        thr, process, basis = PHOTOLYSIS[f]
        entry = {"formula": r.formula, "threshold_nm": thr, "process": process, "basis": basis}
        (absorbers if lam <= thr else below).append(entry)
    initiated = bool(absorbers) and P > 0
    q = photon_flux_mol_s(P, lam)
    formulas = {r.formula for r in reagents}
    chain = next((y for pair, y in CHAIN_YIELD.items() if pair <= formulas), None)
    phi = p["quantum_yield"] or chain or 1.0
    n_lim = min((r.moles for r in reagents if r.formula in {a["formula"] for a in absorbers}), default=None)
    t_conv = n_lim / (q * phi) if initiated and n_lim else None

    notes = []
    if not absorbers:
        notes.append(f"Ни один реагент не фотолизуется при {lam:g} нм"
                     + (": " + ", ".join(f"{b['formula']} - только до {b['threshold_nm']} нм" for b in below)
                        if below else " (нет поглощающих реагентов в таблице фотолиза)")
                     + ". Свет не инициирует реакцию")
    elif P <= 0:
        notes.append("intensity_W = 0: свет выключен")
    else:
        notes.append(f"Фотоинициирование: {', '.join(a['process'] for a in absorbers)} "
                     f"(квант {photon_energy_kJ(lam):.0f} кДж/моль при {lam:g} нм)")
        if t_conv is not None:
            notes.append(f"Поток фотонов {q:.3g} моль/с, квантовый выход {phi:g}"
                         f"{' (цепная реакция, оценка)' if chain and not p['quantum_yield'] else ''}: "
                         f"превращение ~{t_conv:.3g} с, если весь свет поглощен")
            if p["duration_s"] is not None and p["duration_s"] < t_conv:
                notes.append(f"За {p['duration_s']:g} с превратится не более ~{p['duration_s'] / t_conv:.0%} "
                             "лимитирующего реагента: показан равновесный итог")
    return {
        "method": "photochemical", "wavelength_nm": lam, "intensity_W": P,
        "photon_energy_kJ_mol": round(photon_energy_kJ(lam), 1), "photon_flux_mol_s": q,
        "absorbers": absorbers, "non_absorbing": below, "initiated": initiated,
        "quantum_yield": phi, "conversion_time_s": t_conv, "notes": notes,
        "lifts": ["gas_mix_no_igniter"] if initiated else [],
    }
