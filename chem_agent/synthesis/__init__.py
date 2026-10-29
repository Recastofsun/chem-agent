"""Методы синтеза (ТЗ v2.5, W-05...W-09): conditions.method = {"type": ..., параметры}.

Метод не меняет термодинамику объема, а снимает или задает кинетические ограничения и добавляет
в результат отчет метода (result["synthesis"]). Методы с горячими точками (сонохимия, механохимия)
возвращают zone: агент досчитывает равновесие в зоне и, если там идет реакция, отдает ее
закаленные продукты (merge_zone).
"""
from __future__ import annotations

from . import hydrothermal, mechanochemical, photochemical, sol_gel, sonochemical

METHODS = {"photochemical": photochemical, "sonochemical": sonochemical,
           "hydrothermal": hydrothermal, "mechanochemical": mechanochemical, "sol_gel": sol_gel}


class MethodError(ValueError):
    pass


def validate_method(method) -> dict | None:
    """conditions.method: строка-тип или объект с type. -> нормализованный объект."""
    if method is None:
        return None
    if isinstance(method, str):
        method = {"type": method}
    if not isinstance(method, dict) or not method.get("type"):
        raise MethodError("method: объект с полем type")
    t = str(method["type"]).lower().replace("-", "_")
    if t not in METHODS:
        raise MethodError(f"method.type: одно из {tuple(METHODS)} (получено {method['type']!r})")
    return {"type": t, **METHODS[t].validate({k: v for k, v in method.items() if k != "type"})}


def apply_conditions(cond: dict) -> list[str]:
    """Метод задает условия расчета (гидротермальный - T и P автоклава). -> предупреждения."""
    m = cond.get("method")
    mod = METHODS.get(m["type"]) if m else None
    return mod.apply_conditions(m, cond) if mod and hasattr(mod, "apply_conditions") else []


def analyze(method: dict | None, reagents, T: float, cond: dict | None = None):
    """-> отчет метода (dict) или None. reagents - список search.rules.Reagent."""
    if not method:
        return None
    return METHODS[method["type"]].analyze(method, reagents, T, cond)


def zone_request(raw: dict, zone: dict) -> dict | None:
    """Запрос на равновесие в зоне: сухая система при T и P зоны, без растворенных реагентов.
    Закрытая: в открытой сухой системе солвер держит P газов ~0, и при 1900 K CO2 распадается на CO + O2."""
    reag = [r for r in raw["reagents"] if r.get("phase") in ("s", "l", "g") and str(r.get("formula")) != "H2O"]
    if not reag:
        return None
    drop = ("method", "solvent", "pH", "temperature_profile", "water_kg", "atmosphere")
    cond = {k: v for k, v in (raw.get("conditions") or {}).items() if k not in drop}
    cond.update({"temperature_K": zone["T_K"], "solvent": "none"})  # закрыто: в пузырьке газ под давлением
    if zone.get("P_bar"):
        cond["pressure_atm"] = zone["P_bar"] / 1.01325
    opts = {**(raw.get("options") or {}), "include_uncertainty": False}
    return {"reagents": reag, "conditions": cond, "known_energies": raw.get("known_energies") or {},
            "constraints": raw.get("constraints") or {}, "options": opts}


def _summary(d: dict) -> dict:
    return {"status": d.get("status"), "main_product": (d.get("summary") or {}).get("main_product"),
            "equation": ((d.get("balanced_equations") or [{}])[0]).get("equation")}


def merge_zone(bulk: dict, hot: dict, zone: dict) -> dict:
    """Реакция в зоне идет и дает другое, чем объем, - итог: закаленные продукты зоны.
    Иначе - результат объема. Сводка обоих - в synthesis."""
    rep = bulk["synthesis"]
    rep["bulk_result"], rep["zone_result"] = _summary(bulk), _summary(hot)
    hot_ok = (hot.get("summary") or {}).get("reaction_occurred")
    if not (hot_ok and rep["zone_result"]["main_product"] != rep["bulk_result"]["main_product"]):
        rep["used"] = "bulk"
        rep["notes"].append(f"В зоне ({zone['label']}, {zone['T_K']:.0f} K) "
                            + ("реакция та же, что в объеме" if hot_ok else "реакция не идет")
                            + ": результат - равновесие в объеме")
        return bulk
    rep["used"] = "zone"
    note = (f"Продукты образуются в зоне ({zone['label']}, {zone['T_K']:.0f} K) и закаливаются. "
            f"В объеме при {bulk['system']['T_K']:.4g} K: " + (rep["bulk_result"]["equation"] or "реакция не идет")
            + ". Неравновесный результат: продукт метастабилен при условиях объема")
    rep["notes"].append(note)
    out = dict(hot)
    for k in ("reaction_id", "input_hash", "input", "options"):
        out[k] = bulk[k]
    out["warnings"] = list(dict.fromkeys(bulk["warnings"] + [note] + hot["warnings"]))
    out["explanation"] = ((bulk.get("explanation") or []) + [{"step": "Зона метода синтеза", "text": note}]
                          + [{**e, "step": "Зона: " + e["step"]} for e in hot.get("explanation") or []])
    out["synthesis"] = rep
    methods = bulk["metadata"]["methods_used"] + hot["metadata"]["methods_used"] + ["Hot-spot zone + quench"]
    out["metadata"] = {**hot["metadata"], "methods_used": list(dict.fromkeys(methods))}
    return out
