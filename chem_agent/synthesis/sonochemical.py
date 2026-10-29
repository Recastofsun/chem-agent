"""Сонохимический метод (W-06): параметры frequency_kHz, power_W (ТЗ).

Модель горячих точек (hot-spot). Ультразвук в жидкости вызывает кавитацию: пузырек схлопывается
почти адиабатически. Измеренные температуры (Suslick, Flint 1991, Nature 353:414): газ внутри
пузырька ~5000 K, жидкая оболочка и поверхность частиц ~1900 K, время ~1 мкс, охлаждение ~1e10 K/с.
Реакция считается дважды:
- объем при T - обычное равновесие;
- зона кавитации: сухая открытая система при T_zone = 1900 K (твердые частицы на границе пузырька,
  газы уходят в пузырек). Продукты зоны закаливаются и сохраняются, даже если в объеме они
  термодинамически невыгодны (CaCO3 + SiO2 -> CaSiO3 + CO2 при 298 K: ΔG = +41 кДж/моль).
Условия кавитации: есть жидкость; амплитуда звукового давления P_a = sqrt(2·ρ·c·I) выше внешнего
давления (порог Блейка, грубо); частота 16 кГц - 2 МГц (на мегагерцах пузырек не успевает вырасти).
Скорость: выход Y ~ 1e-9 моль/Дж (порядок сонохимических выходов), время превращения n / (Y·P).
"""
from __future__ import annotations

RHO_C_WATER = 1000.0 * 1482.0  # кг/(м2 с), акустический импеданс воды
T_SHELL_K = 1900.0             # жидкая оболочка / поверхность частиц (Suslick, Flint 1991)
T_GAS_K = 5000.0               # газ внутри пузырька, для отчета
F_MIN_KHZ, F_MAX_KHZ = 16.0, 2000.0
YIELD_MOL_J = 1e-9             # порядок выхода сонохимических реакций, моль/Дж

DEFAULTS = {"frequency_kHz": None, "power_W": 100.0, "horn_area_cm2": 1.0, "duration_s": None}


def validate(p: dict) -> dict:
    from ..parser.validator import ValidationError, _num
    out = {**DEFAULTS, **p}
    if out["frequency_kHz"] is None:
        raise ValidationError("method.frequency_kHz: обязательный параметр сонохимического метода")
    out["frequency_kHz"] = _num(out["frequency_kHz"], "method.frequency_kHz", lo=1.0, hi=1e5)
    out["power_W"] = _num(out["power_W"], "method.power_W", lo=0.0, hi=1e5)
    out["horn_area_cm2"] = _num(out["horn_area_cm2"], "method.horn_area_cm2", lo=1e-3, hi=1e4)
    out["duration_s"] = _num(out["duration_s"], "method.duration_s", lo=0.0, allow_none=True)
    return out


def pressure_amplitude_bar(power_W: float, area_cm2: float) -> float:
    intensity = power_W / (area_cm2 * 1e-4)  # Вт/м2
    return (2.0 * RHO_C_WATER * intensity) ** 0.5 / 1e5


def analyze(p: dict, reagents, T: float, cond: dict | None = None) -> dict:
    cond = cond or {}
    f, P = p["frequency_kHz"], p["power_W"]
    liquid = (cond.get("solvent") or {}).get("name") == "water" or any(r.phase == "l" for r in reagents)
    P_ext = float(cond.get("pressure_atm") or 1.0) * 1.01325
    Pa = pressure_amplitude_bar(P, p["horn_area_cm2"])
    reason = None
    if not liquid:
        reason = "нет жидкости: ультразвук в сухой смеси не вызывает кавитации"
    elif f < F_MIN_KHZ:
        reason = f"{f:g} кГц - ниже 16 кГц, это слышимый звук, а не ультразвук"
    elif f > F_MAX_KHZ:
        reason = f"{f:g} кГц выше {F_MAX_KHZ:g} кГц: пузырьки не успевают вырасти за полупериод"
    elif Pa <= P_ext:
        reason = f"амплитуда давления {Pa:.2g} бар не выше внешнего {P_ext:.3g} бар (порог Блейка)"
    cav = reason is None
    solids = [r for r in reagents if r.phase in ("s", "l", "g")]
    n = sum(r.moles for r in solids)
    t_conv = n / (YIELD_MOL_J * P) if cav and n and P > 0 else None
    notes = []
    if not cav:
        notes.append("Кавитации нет - " + reason + ". Результат - обычное равновесие")
    else:
        notes.append(f"Кавитация при {f:g} кГц, {P:g} Вт: амплитуда давления {Pa:.3g} бар. Горячие точки: "
                     f"газ ~{T_GAS_K:.0f} K, поверхность частиц ~{T_SHELL_K:.0f} K, закалка ~1e10 K/с")
        if t_conv is not None:
            notes.append(f"Оценка времени обработки ~{t_conv:.2g} с (выход ~{YIELD_MOL_J:g} моль/Дж, порядок величины)")
            if p["duration_s"] is not None and p["duration_s"] < t_conv:
                notes.append(f"За {p['duration_s']:g} с превратится ~{p['duration_s'] / t_conv:.0%}: показан "
                             "итог полной обработки")
    zone = {"T_K": T_SHELL_K, "label": "зона кавитации, поверхность частиц", "quench": True} \
        if cav and solids else None
    return {"method": "sonochemical", "frequency_kHz": f, "power_W": P, "pressure_amplitude_bar": Pa,
            "cavitation": cav, "hot_spot_gas_K": T_GAS_K if cav else None,
            "hot_spot_shell_K": T_SHELL_K if cav else None, "conversion_time_s": t_conv,
            "notes": notes, "zone": zone, "initiated": False}
