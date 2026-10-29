"""Markdown report (UTF-8 without BOM)."""
from __future__ import annotations

from pathlib import Path

from ..utils.encoding import write_text
from .fmt import num, pct, pm


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def render(d: dict) -> str:
    s = d.get("summary") or {}
    L = [f"# Отчет chem-agent: {', '.join(r['formula'] for r in d['input']['reagents'])}", ""]
    L.append(f"ID: `{d['reaction_id']}`  ")
    L.append(f"Хэш входа (sha256): `{d['input_hash']}`")
    L += ["", "## 1. Резюме", ""]
    if d["status"] == "unknown":
        L.append(f"**{d['message']}**")
    elif d["status"] == "no_reaction":
        L.append("**Реакция не идет при заданных условиях.**")
    else:
        L.append(f"- Основной продукт: **{s.get('main_product')}**")
        L.append(f"- ΔG реакции: {pm(s.get('delta_G_kJ_mol'), s.get('delta_G_uncertainty'))} кДж/моль")
        L.append(f"- Уверенность: {pct(s.get('confidence'))}")
        if s.get("pH") is not None:
            L.append(f"- pH после реакции: {num(s['pH'], 3)}")
    L.append(f"- Время расчета: {num(d['metadata'].get('compute_time_s'), 3)} с")
    L += ["", "## 2. Входные данные", ""]
    L.append(_table(["Реагент", "Фаза", "Моль"], [[r["formula"], r["phase"], num(r["moles"])]
                                                 for r in d["input"]["reagents"]]))
    c = d["input"]["conditions"]
    L += ["", f"T = {num(c['temperature_K'])} K; P = {num(c['pressure_atm'])} атм; объем {num(c['volume_L'])} л; "
              f"растворитель: {c['solvent']['name']}", ""]
    L.append(_table(["Уровень", "Источник энергии", "Доступен", "Использован", "Комментарий"],
                    [[str(x["level"]), x["source"], "да" if x["available"] else "нет",
                      "да" if x["used"] else "нет", x["note"]] for x in d["energy_chain"]]))
    L += ["", "## 3. Возможные реакции", ""]
    if d["balanced_equations"]:
        L.append(_table(["Уравнение", "ΔG, кДж/моль", "lg K", "Выполнима", "Уверенность"],
                        [[e["equation"], pm(e["delta_G_kJ_mol"], e["delta_G_uncertainty"]),
                          pm(e.get("log10_K"), e.get("log10_K_uncertainty")),
                          "да" if e["feasible"] else "нет", pct(e.get("confidence"))]
                         for e in d["balanced_equations"]]))
        if d.get("ionic_equation"):
            L += ["", f"Ионное уравнение: `{d['ionic_equation']['equation']}`"]
    else:
        L.append("Реакций нет.")
    L += ["", "## 4. Продукты", ""]
    if d["products"]:
        L.append(_table(["Формула", "Вид", "Моль", "Масса, г", "ΔGf(T), кДж/моль", "Источник", "Активность", "SI"],
                        [[p["formula"], p["kind_ru"], num(p["moles"]), num(p["mass_g"]),
                          pm(p["delta_Gf_kJ_mol"], p["uncertainty"]), p["source"], num(p["activity"]),
                          num(p["saturation_index"], 3) if p["saturation_index"] is not None else "-"]
                         for p in d["products"]]))
    else:
        L.append("Новых веществ нет.")
    L += ["", "Итоговый состав (основные частицы):", ""]
    L.append(_table(["Частица", "Фаза", "Было, моль", "Стало, моль", "Изменение"],
                    [[r["formula"], r["phase"], num(r["initial_mol"]), num(r["final_mol"]), num(r["change_mol"])]
                     for r in (d.get("final_composition") or [])[:15]]))
    L += ["", "## 5. Термодинамика", ""]
    th = d.get("thermo") or {}
    if th.get("dG_T"):
        L.append(_table(["T, K", "ΔG, кДж/моль", "lg K"],
                        [[num(x["T_K"]), pm(x["delta_G_kJ_mol"], x["sigma"]), num(x["log10_K"])]
                         for x in th["dG_T"][::3]]))
    if th.get("profile"):
        L += ["", "Температурный профиль:", ""]
        L.append(_table(["T, K", "t, с", "pH", "Продукты, моль"],
                        [[num(x["T_K"]), num(x.get("t_s")), num(x.get("pH")),
                          "; ".join(f"{k}: {num(v)}" for k, v in (x.get("products") or {}).items())]
                         for x in th["profile"]]))
    L += ["", "## 6. Кинетика", ""]
    k = d.get("kinetics")
    if k:
        L.append(f"- Модель: {k['model']}")
        L.append(f"- Барьер: {pm(k['barrier_kJ_mol'], k['uncertainty'])} кДж/моль")
        L.append(f"- Константа скорости: {num(k['rate_constant'])} {k['rate_constant_units']}")
        L.append(f"- Период полупревращения: {num(k['half_life_s'])} с")
        if k.get("note"):
            L.append(f"- {k['note']}")
    else:
        L.append("Кинетика не рассчитывалась.")
    L += ["", "## 7. Неопределенность", ""]
    u = d.get("uncertainty")
    if u:
        L.append(f"Метод: {u['method']}, членов ансамбля: {u['members']}. Уверенность {pct(u['confidence'])} "
                 f"({u['confidence_definition']}).")
        if u.get("products"):
            L += ["", _table(["Продукт", "Среднее, моль", "σ, моль", "5-95 %"],
                             [[p["formula"], num(p["mean"]), num(p["std"]), f"{num(p['p05'])} - {num(p['p95'])}"]
                              for p in u["products"]])]
        if u.get("contributions"):
            L += ["", "Вклад источников в погрешность ΔG:", ""]
            L.append(_table(["Частица", "Источник", "σ, кДж/моль", "Доля"],
                            [[c["species"], c["source"], num(c["sigma_kJ"]), pct(c["share"])]
                             for c in u["contributions"]]))
    else:
        L.append("Не рассчитывалась.")
    L += ["", "## 8. Объяснение", ""]
    for i, e in enumerate(d.get("explanation") or [], 1):
        L.append(f"{i}. **{e['step']}.** {e['text']}")
    if d.get("warnings"):
        L += ["", "Предупреждения:", ""]
        L += [f"- {w}" for w in dict.fromkeys(d["warnings"])]
    m = d["metadata"]
    L += ["", "## 9. Метаданные", "",
          f"- Версия: {m['version']}; офлайн: {'да' if m['offline'] else 'нет'}",
          f"- Методы: {', '.join(m.get('methods_used') or [])}",
          f"- Платформа: {m['platform']}; Python {m['python']}",
          f"- База: {m['database'].get('built_from', '')}", ""]
    return "\n".join(L)


def save(d: dict, path: Path) -> Path:
    return write_text(path, render(d))
