"""Оркестратор Pipeline (W-04): 5 этапов, ранний выход, тупик, fallback.

compact (по умолчанию): один расчет полного равновесия, как до v2.5. Этапы считаются только
  если он не сошелся - как теплый старт для повторного расчета.
detailed: этапы 1-4 считаются всегда, отчет по ним уходит в explanation и result["pipeline"].

Финал (этап 5) всегда - обычный полный расчет, поэтому итоговый состав в обоих режимах одинаков.
Тупик: этап 3 не сошелся - пробуем порядок 1-2-4-3. Полный расчет не сошелся - повтор
с теплого старта от последнего сошедшегося этапа. Не помогло и равновесия нет - status unknown
(уравнение при найденном равновесии подбирает staged balancer, W-02).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..thermo.equilibrium import EquilibriumError
from .stages import (ALT_ORDER, AQ, COND, DEFAULT_ORDER, GAS, STAGES, dissociation_mask, formed, kind_mask,
                     particles, reagents_consumed, shift_for, supersaturated)

MODES = ("compact", "detailed")


@dataclass
class PipelineResult:
    eq: object                     # EqResult финала или None
    b_used: np.ndarray | None
    status: str                    # "ok" | "unknown"
    report: dict = field(default_factory=dict)
    error: str | None = None


class _DeadEnd(Exception):
    pass


def _solve(solver, mask, warm=None):
    try:
        return solver.run(dG_shift=shift_for(solver, mask), warm=warm)
    except EquilibriumError:
        return None


def _entry(sid: int, status: str, **kw) -> dict:
    st = STAGES[sid]
    return {"stage": sid, "name": st.name, "title": st.title, "status": status, **kw}


def _done(sid, eq, system, prev_n, **kw) -> dict:
    return _entry(sid, "done", converged=bool(eq.converged), residual=float(eq.residual),
                  iterations=int(eq.iterations), formed=formed(system, eq, prev_n), **kw)


def run_stages(solver, order=DEFAULT_ORDER):
    """Этапы 1-4 в заданном порядке. -> (отчеты, последнее сошедшееся равновесие, маска, ранний выход)."""
    system = solver.system
    mask = dissociation_mask(system)
    eq = _solve(solver, mask)
    if eq is None:
        return [_entry(1, "failed", reason="равновесие этапа не найдено")], None, mask, False
    if system.aqueous:
        first = _entry(1, "done", converged=bool(eq.converged), residual=float(eq.residual),
                       iterations=int(eq.iterations), formed=particles(system, eq, mask))
    else:
        first = _entry(1, "skipped", reason="нет растворителя: диссоциации нет")
    reports, last = [first], eq
    if reagents_consumed(system, eq):
        for sid in order[1:4]:
            reports.append(_entry(sid, "skipped", reason="ранний выход: реагенты израсходованы на этапе 1"))
        return reports, last, mask, True

    for sid in order[1:4]:
        sat, unknown = [], False
        if sid == 2:
            if not system.aqueous:
                reports.append(_entry(2, "skipped", reason="нет растворителя"))
                continue
            cand = mask | kind_mask(system, AQ)
        else:
            kind = COND if sid == 3 else GAS
            sat, unknown = supersaturated(solver, last, mask, kind)
            if not sat and not unknown:
                reports.append(_entry(sid, "skipped", reason="пересыщенных твердых фаз нет" if sid == 3
                                      else "давление газов ниже внешнего"))
                continue
            cand = mask | kind_mask(system, kind)
        eq = _solve(solver, cand, warm=last)
        if eq is None or not eq.converged:
            if sid == 3 and tuple(order) == DEFAULT_ORDER:
                raise _DeadEnd
            reports.append(_entry(sid, "failed", reason="равновесие этапа не сошлось", supersaturated=sat[:5]))
            continue
        reports.append(_done(sid, eq, system, last.n, supersaturated=sat[:5]))
        mask, last = cand, eq
    return reports, last, mask, False


def run(solver, final: Callable, mode: str = "compact") -> PipelineResult:
    """final(warm) -> (eq, b_used): полный расчет агента (с pH-статом, если задан)."""
    report = {"mode": mode, "order": None, "early_exit": False, "fallback": None, "stages": []}
    eq, b_used, err = None, None, None
    try:
        eq, b_used = final(None)
    except EquilibriumError as e:
        err = str(e)
    ok = eq is not None and eq.converged
    if mode == "compact" and ok:
        return PipelineResult(eq, b_used, "ok", report)

    order = DEFAULT_ORDER
    try:
        stages, last, mask, early = run_stages(solver, order)
    except _DeadEnd:
        order = ALT_ORDER
        stages, last, mask, early = run_stages(solver, order)
    report.update(order=list(order), early_exit=early, stages=stages)

    if not ok and last is not None:
        try:
            eq2, b2 = final(last)
        except EquilibriumError:
            eq2, b2 = None, None
        if eq2 is not None and (eq is None or eq2.converged or eq2.residual < eq.residual):
            eq, b_used = eq2, b2
            report["fallback"] = "warm_restart"
    if eq is None:
        report["fallback"] = "unknown"
        report["stages"].append(_entry(5, "failed", reason=err or "равновесие не найдено"))
        return PipelineResult(None, None, "unknown", report, err)
    report["stages"].append(_done(5, eq, solver.system, last.n if last is not None else solver.system.initial))
    return PipelineResult(eq, b_used, "ok", report)


def _fmt(items) -> str:
    return ", ".join(f"{x['formula']} {x['moles']:.3g} моль" for x in items)


def explain(report: dict) -> list[dict]:
    """Шаги explanation для режима detailed."""
    out = []
    if report.get("order") and tuple(report["order"]) != DEFAULT_ORDER:
        out.append({"step": "Pipeline: тупик", "text": "Этап осаждения не сошелся, порядок изменен: "
                    + " -> ".join(str(s) for s in report["order"])})
    for s in report.get("stages") or []:
        step = f"Pipeline, этап {s['stage']}: {s['title']}"
        if s["status"] == "skipped":
            text = "пропущен - " + s["reason"]
        elif s["status"] == "failed":
            text = "не выполнен - " + s["reason"]
        else:
            parts = []
            if s.get("supersaturated"):
                parts.append("пересыщены: " + ", ".join(f"{f} ({'SI' if s['stage'] == 3 else 'lg p/P'} {a:g})"
                                                       for f, a in s["supersaturated"]))
            label = "частицы в растворе: " if s["stage"] == 1 else "образовались: "
            parts.append((label + _fmt(s["formed"])) if s["formed"] else "состав не изменился")
            if not s["converged"]:
                parts.append(f"не сошлось, невязка {s['residual']:.1e}")
            text = "; ".join(parts)
        out.append({"step": step, "text": text, "pipeline_stage": s["stage"]})
    if report.get("fallback") == "warm_restart":
        out.append({"step": "Pipeline: повторный расчет",
                    "text": "Полный расчет не сошелся с нуля, повторен от состава последнего этапа"})
    return out
