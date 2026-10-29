"""Гидротермальный метод (W-07): параметры T_K, autoclave_P_bar (ТЗ).

Автоклав: вода остается жидкой выше 100 °C, потому что давление не ниже давления насыщенного пара.
Метод задает T и P расчета (conditions.temperature_K, pressure_atm) и проверяет состояние воды:
- P_sat(T) - IAPWS-IF97, область 4 (уравнение насыщения);
- заданное давление ниже P_sat - в закрытом автоклаве оно автогенное, принимается P_sat;
- T выше критической (647,096 K) - сверхкритический флюид, модель жидкой воды не применима.
Кинетику метод не трогает напрямую: правила с Ea по Эйрингу (W-03) сами снимаются при высокой T
(aluminosilicate_lowT - при T > 423 K).
"""
from __future__ import annotations

import math

T_CRIT_K = 647.096
P_CRIT_BAR = 220.64
_N = (0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2, 0.12020824702470e5,
      -0.32325550322333e7, 0.14915108613530e2, -0.48232657361591e4, 0.40511340542057e6,
      -0.23855557567849, 0.65017534844798e3)

DEFAULTS = {"T_K": None, "autoclave_P_bar": None}


def p_sat_bar(T: float) -> float:
    """Давление насыщенного пара воды, бар (IAPWS-IF97, 273,15-647,096 K)."""
    n = _N
    th = T + n[8] / (T - n[9])
    A = th * th + n[0] * th + n[1]
    B = n[2] * th * th + n[3] * th + n[4]
    C = n[5] * th * th + n[6] * th + n[7]
    return (2 * C / (-B + math.sqrt(B * B - 4 * A * C))) ** 4 * 10.0


def validate(p: dict) -> dict:
    from ..parser.validator import ValidationError, _num
    out = {**DEFAULTS, **p}
    if out["T_K"] is None:
        raise ValidationError("method.T_K: обязательный параметр гидротермального метода")
    out["T_K"] = _num(out["T_K"], "method.T_K", lo=273.15, hi=1273.15)
    out["autoclave_P_bar"] = _num(out["autoclave_P_bar"], "method.autoclave_P_bar", lo=0.0, hi=5000.0,
                                  allow_none=True)
    return out


def apply_conditions(p: dict, cond: dict) -> list[str]:
    """Задает T и P расчета. -> предупреждения."""
    from ..parser.validator import ValidationError
    if (cond.get("solvent") or {}).get("name") != "water":
        raise ValidationError("гидротермальный метод: нужен растворитель water")
    T, P = p["T_K"], p["autoclave_P_bar"]
    notes = []
    if T < T_CRIT_K:
        ps = p_sat_bar(T)
        if P is None:
            P = ps
            notes.append(f"Давление в автоклаве не задано: принято давление насыщенного пара {ps:.3g} бар")
        elif P < ps:
            notes.append(f"autoclave_P_bar = {P:g} бар ниже давления пара воды при {T:g} K ({ps:.3g} бар): "
                         f"в закрытом автоклаве давление автогенное, принято {ps:.3g} бар")
            P = ps
    elif P is None:
        P = P_CRIT_BAR
    p["P_bar_used"] = P
    cond["temperature_K"] = T
    cond["pressure_atm"] = P / 1.01325
    return notes


def analyze(p: dict, reagents, T: float, cond: dict | None = None) -> dict:
    P = p.get("P_bar_used") or p.get("autoclave_P_bar")
    notes, state = [], "liquid"
    if T >= T_CRIT_K:
        state = "supercritical"
        notes.append(f"T = {T:g} K выше критической точки воды ({T_CRIT_K} K): сверхкритический флюид, "
                     "модели жидкой воды (активности, диэлектрическая проницаемость) не применимы")
    else:
        ps = p_sat_bar(T)
        notes.append(f"Гидротермальные условия: {T:g} K ({T - 273.15:.0f} °C), {P:.3g} бар; "
                     f"давление пара воды {ps:.3g} бар - вода жидкая")
        if T > 373.15:
            notes.append("Параметры Pitzer и константы комплексов - при 298 K; при высокой T активности - оценка")
    return {"method": "hydrothermal", "T_K": T, "P_bar": P, "p_sat_bar": p_sat_bar(T) if T < T_CRIT_K else None,
            "water_state": state, "notes": notes, "initiated": False, "zone": None}
