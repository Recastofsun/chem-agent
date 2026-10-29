"""Разделение продуктов (W-13, ТЗ 14.3): фильтрация, центрифугирование, дистилляция.

Работает по равновесному составу результата (final_composition), ничего не пересчитывает:
- filtration: твердые фазы - осадок на фильтре, раствор и растворитель - фильтрат. Студенистые гидроксиды
  (Fe(OH)3, Al(OH)3 и т. п.) фильтруются медленно - предупреждение;
- centrifugation: то же разделение по плотности, плюс отдельный слой несмешивающихся жидкостей (Br2, Hg);
- distillation: жидкая часть делится по температуре кипения. Tb оценивается из базы:
  Tb ≈ ΔHисп / ΔSисп, ΔHисп = ΔHf(g) - ΔHf(l), ΔSисп = (ΔHисп - ΔGисп(298)) / 298,15 (вода: 369 K при 373 K
  по справочнику, этанол 355 K при 351 K). Компоненты легче растворителя (на 5 K и более) - дистиллят,
  растворенные газы - отгоняются первыми, соли и нелетучее - кубовый остаток. Азеотропы не моделируются.
"""
from __future__ import annotations

from .parser.formula import parse_formula

METHODS = ("filtration", "centrifugation", "distillation")
GELATINOUS = {"Fe(OH)3", "Al(OH)3", "Cr(OH)3", "Cu(OH)2", "Zn(OH)2", "Mn(OH)2", "Fe(OH)2", "Ni(OH)2"}
WATER = "H2O"
PRESENT = 1e-9


def boiling_point_K(db, formula: str) -> float | None:
    """Оценка Tb по жидкой и газовой записи базы; None - если одной из них нет."""
    key = parse_formula(formula).key
    l = [s for s in db.species if s.key == key and s.phase == "l"]
    g = [s for s in db.species if s.key == key and s.phase == "g"]
    if not l or not g or l[0].dHf is None or g[0].dHf is None:
        return None
    dH = g[0].dHf - l[0].dHf
    dS = (dH - (g[0].dGf - l[0].dGf)) / 298.15
    return dH / dS if dS > 1e-6 else None


def _label(formula: str) -> str:
    from .parser.naming import ORGANIC_DISPLAY
    c = parse_formula(formula)
    org = ORGANIC_DISPLAY.get(tuple((e, int(n)) for e, n in c.key[0])) if c.charge == 0 else None
    return org or formula


def _gas_only(db, formula: str) -> bool:
    key = parse_formula(formula).key
    phases = {s.phase for s in db.species if s.key == key}
    return "g" in phases and not phases & {"l", "s"}


def _rows(result: dict) -> list[dict]:
    """Значимые компоненты: порог ТЗ 11.3 - max(1e-4, 1e-3 от главного) не годится для следов в
    растворе, берется max(1e-7, 1e-4 от крупнейшего компонента, кроме растворителя)."""
    rows = [c for c in result.get("final_composition") or [] if c.get("final_mol", 0) > PRESENT]
    top = max((c["final_mol"] for c in rows if c["formula"] != WATER), default=0.0)
    lim = max(1e-7, 1e-4 * top)
    return [{**c, "formula": _label(c["formula"])} for c in rows
            if c["final_mol"] >= lim or c["formula"] == WATER]


def _frac(name: str, rows: list[dict], note: str | None = None) -> dict:
    return {"fraction": name, "components": [{"formula": c["formula"], "phase": c["phase"],
                                              "moles": c["final_mol"]} for c in rows], "note": note}


def filtration(result: dict, centrifuge: bool = False) -> dict:
    rows = _rows(result)
    solids = [c for c in rows if c["phase"] == "s"]
    liquids_sep = [c for c in rows if c["phase"] == "l" and c["formula"] != WATER] if result["system"]["aqueous"] else []
    liquid = [c for c in rows if c["phase"] == "aq" or (c["phase"] == "l" and c not in liquids_sep)]
    gases = [c for c in rows if c["phase"] == "g"]
    notes = []
    gel = sorted({c["formula"] for c in solids} & GELATINOUS)
    if gel:
        notes.append(f"{', '.join(gel)} - студенистый осадок, " +
                     ("уплотняется центрифугированием" if centrifuge else "фильтруется медленно, лучше центрифугировать"))
    if not solids:
        notes.append("Твердой фазы нет: " + ("осадок не отделяется" if centrifuge else "на фильтре ничего не остается"))
    fr = [_frac("осадок" if not centrifuge else "осадок (на дне)", solids),
          _frac("фильтрат" if not centrifuge else "надосадочная жидкость", liquid)]
    if centrifuge and liquids_sep:
        fr.append(_frac("отдельный жидкий слой", liquids_sep, "несмешивающаяся с водой жидкость"))
    elif liquids_sep:
        fr[1]["components"] += _frac("", liquids_sep)["components"]
        notes.append("Несмешивающаяся жидкость проходит через фильтр вместе с раствором: нужна делительная воронка")
    if gases:
        fr.append(_frac("газ (уходит)", gases))
    return {"method": "centrifugation" if centrifuge else "filtration", "fractions": fr, "notes": notes}


def distillation(result: dict, db) -> dict:
    rows = [c for c in _rows(result) if c["phase"] in ("aq", "l", "g")]
    tb_solvent = boiling_point_K(db, WATER) if result["system"]["aqueous"] else None
    volatile, residue, gas, notes = [], [], [], []
    for c in rows:
        if c["phase"] == "g":
            gas.append({**c, "Tb_K": None})
            continue
        comp = parse_formula(c["formula"])
        tb = boiling_point_K(db, c["formula"]) if comp.charge == 0 else None
        if c["formula"] == WATER:
            continue
        if tb is None and comp.charge == 0 and _gas_only(db, c["formula"]):
            gas.append({**c, "Tb_K": None})
        elif tb is None:
            residue.append({**c, "Tb_K": None})
        elif tb < 273.15:
            gas.append({**c, "Tb_K": round(tb, 1)})
        elif tb_solvent is None or tb < tb_solvent - 5:
            volatile.append({**c, "Tb_K": round(tb, 1)})
        else:
            residue.append({**c, "Tb_K": round(tb, 1)})
    volatile.sort(key=lambda c: c["Tb_K"])
    fr = []
    if gas:
        fr.append({"fraction": "растворенные газы (отгоняются первыми)",
                   "components": [{"formula": c["formula"], "phase": c["phase"], "moles": c["final_mol"],
                                   "Tb_K": c["Tb_K"]} for c in gas], "note": None})
    for c in volatile:
        fr.append({"fraction": f"дистиллят ~{c['Tb_K']:.0f} K", "components": [
            {"formula": c["formula"], "phase": c["phase"], "moles": c["final_mol"], "Tb_K": c["Tb_K"]}], "note": None})
    if tb_solvent:
        w = next((c for c in rows if c["formula"] == WATER), None)
        if w:
            fr.append({"fraction": f"растворитель ~{tb_solvent:.0f} K", "components": [
                {"formula": WATER, "phase": "l", "moles": w["final_mol"], "Tb_K": round(tb_solvent, 1)}], "note": None})
    fr.append({"fraction": "кубовый остаток", "components": [
        {"formula": c["formula"], "phase": c["phase"], "moles": c["final_mol"], "Tb_K": c["Tb_K"]} for c in residue],
        "note": "соли, ионы и нелетучие вещества"})
    if volatile and tb_solvent:
        notes.append("Азеотропы не моделируются (этанол - вода: 95,6 % при 351 K); разделение - идеальное")
    if not volatile and not gas:
        notes.append("Летучих компонентов легче растворителя нет: отгоняется только растворитель")
    notes.append("Tb - оценка из ΔHисп/ΔSисп базы при 298 K, точность около ±5 K")
    return {"method": "distillation", "fractions": fr, "notes": notes}


def separate(result: dict, methods: list[str], db) -> list[dict]:
    out = []
    for m in methods:
        if m == "filtration":
            out.append(filtration(result))
        elif m == "centrifugation":
            out.append(filtration(result, centrifuge=True))
        elif m == "distillation":
            out.append(distillation(result, db))
    return out
