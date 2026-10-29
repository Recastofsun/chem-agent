"""Механохимический метод (W-08): параметры rpm, ball_material (ТЗ).

Модель вспышечной температуры (flash temperature, Schwarz & Koch 1986): при ударе шара порошок в зоне
контакта кратковременно (~1e-5 с) разогревается на ΔT, продукты закаливаются массой шара и барабана.
Скорость шара v = π·D·rpm/60 (D - диаметр барабана). Оценка
    ΔT = ΔT_REF · (v / V_REF) · sqrt(ρ_шара / ρ_стали),
калибровка: ΔT_REF = 700 K при 5 м/с для стальных шаров (оценки вспышки в планетарных мельницах -
сотни K). Мокрый помол (растворитель water) охлаждает зону: ΔT x 0,5.
Реакция считается в зоне при T + ΔT (общий механизм зон, как в W-06), если там идет - закаленный продукт.
Значения - порядок величины, не модель конкретной мельницы.
"""
from __future__ import annotations

import math

BALL_DENSITY = {  # г/см3
    "steel": 7.85, "stainless_steel": 7.9, "tungsten_carbide": 15.6, "zirconia": 5.7,
    "agate": 2.65, "alumina": 3.95, "silicon_nitride": 3.2,
}
RHO_STEEL = 7.85
DT_REF_K, V_REF = 700.0, 5.0
WET_FACTOR = 0.5
CONTAMINATION = {"agate": "SiO2", "alumina": "Al2O3", "zirconia": "ZrO2", "tungsten_carbide": "WC",
                 "steel": "Fe", "stainless_steel": "Fe, Cr, Ni"}

DEFAULTS = {"rpm": None, "ball_material": "steel", "mill_diameter_m": 0.1, "milling_time_h": None}


def validate(p: dict) -> dict:
    from ..parser.validator import ValidationError, _num
    out = {**DEFAULTS, **p}
    if out["rpm"] is None:
        raise ValidationError("method.rpm: обязательный параметр механохимического метода")
    out["rpm"] = _num(out["rpm"], "method.rpm", lo=0.0, hi=5000.0)
    out["mill_diameter_m"] = _num(out["mill_diameter_m"], "method.mill_diameter_m", lo=0.01, hi=2.0)
    out["milling_time_h"] = _num(out["milling_time_h"], "method.milling_time_h", lo=0.0, allow_none=True)
    m = str(out["ball_material"]).lower()
    if m not in BALL_DENSITY:
        raise ValidationError(f"method.ball_material: одно из {tuple(BALL_DENSITY)} (получено {out['ball_material']!r})")
    out["ball_material"] = m
    return out


def ball_velocity(rpm: float, diameter_m: float) -> float:
    return math.pi * diameter_m * rpm / 60.0


def flash_dT(rpm: float, material: str, diameter_m: float = 0.1, wet: bool = False) -> float:
    v = ball_velocity(rpm, diameter_m)
    dT = DT_REF_K * (v / V_REF) * math.sqrt(BALL_DENSITY[material] / RHO_STEEL)
    return dT * (WET_FACTOR if wet else 1.0)


def analyze(p: dict, reagents, T: float, cond: dict | None = None) -> dict:
    cond = cond or {}
    wet = (cond.get("solvent") or {}).get("name") == "water"
    v = ball_velocity(p["rpm"], p["mill_diameter_m"])
    dT = flash_dT(p["rpm"], p["ball_material"], p["mill_diameter_m"], wet)
    T_zone = T + dT
    solids = [r for r in reagents if r.phase in ("s", "l")]
    notes = [f"Помол {p['rpm']:g} об/мин, шары {p['ball_material']}: скорость удара {v:.2g} м/с, "
             f"вспышка в зоне контакта +{dT:.0f} K (до {T_zone:.0f} K, оценка)"
             + (", мокрый помол охлаждает зону" if wet else "")]
    if not solids:
        notes.append("Нет твердых реагентов: механическая активация не применима")
    if p["ball_material"] in CONTAMINATION:
        notes.append(f"Износ шаров дает примесь {CONTAMINATION[p['ball_material']]} (не учитывается)")
    if p["milling_time_h"] is not None and p["milling_time_h"] < 1:
        notes.append(f"Время помола {p['milling_time_h']:g} ч: обычно нужны часы, показан итог полной активации")
    zone = {"T_K": round(T_zone, 1), "label": "зона удара шаров", "quench": True} if solids and dT > 1 else None
    return {"method": "mechanochemical", "rpm": p["rpm"], "ball_material": p["ball_material"],
            "ball_velocity_m_s": v, "flash_dT_K": dT, "zone_T_K": T_zone if zone else None,
            "notes": notes, "zone": zone, "initiated": False}
