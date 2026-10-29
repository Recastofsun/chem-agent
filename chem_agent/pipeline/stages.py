"""Этапы Pipeline (W-04, ТЗ v2.5 раздел 3).

Этап - равновесие на подмножестве частиц системы. Подмножества вложены:
1. Диссоциация: реагенты (как каждый из них равновесен с водой до смешивания) + их ионы + H+/OH-/H2O.
2. Комплексообразование: + все частицы раствора (комплексы, ионные пары, гидроксо-формы).
3. Осаждение: + конденсированные фазы, если хотя бы одна пересыщена (SI > 0).
4. Газовыделение: + газы, если равновесное парциальное давление хотя бы одного выше P.
5. Финальное равновесие: все частицы, обычный расчет без ограничений (докрутка).

Частица вне этапа исключается сдвигом ее ΔG на +EXCLUDE_RT·RT: доля exp(-300) ~ 1e-130,
матрица системы и баланс масс не меняются. Этап 5 совпадает с расчетом без Pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..search.staged_balancer import MEDIUM, decompose
from ..thermo.equilibrium import AQ, COND, GAS, SOLVENT
from ..thermo.gibbs import R

EXCLUDE_RT = 300.0     # сдвиг ΔG исключенной частицы, в RT (SI бывает до 30, нужен запас)
LN10 = float(np.log(10.0))
PRESENT = 1e-10        # доля от суммы b, ниже которой частицы считаем отсутствующими
SHOW = 5               # сколько новых частиц показывать в отчете этапа


@dataclass(frozen=True)
class Stage:
    id: int
    name: str
    title: str


STAGES = {
    1: Stage(1, "dissociation", "Диссоциация реагентов"),
    2: Stage(2, "complexation", "Комплексообразование"),
    3: Stage(3, "precipitation", "Осаждение"),
    4: Stage(4, "gas_evolution", "Газовыделение"),
    5: Stage(5, "final", "Финальное равновесие"),
}
DEFAULT_ORDER = (1, 2, 3, 4, 5)
ALT_ORDER = (1, 2, 4, 3, 5)  # тупик на осаждении: сначала газ


def dissociation_mask(system) -> np.ndarray:
    """Этап 1: исходные частицы, ионы реагентов, среда (H+, OH-, H2O) и растворитель."""
    scale = float(np.sum(np.abs(system.b))) or 1.0
    keys = set(MEDIUM)
    for r in system.reagents:
        keys |= set(decompose(r.comp.key))
    mask = np.array([s.key in keys for s in system.species]) | (np.asarray(system.initial) > PRESENT * scale)
    mask |= np.array([k == SOLVENT for k in system.kinds])
    if not system.aqueous:  # без растворителя ионы не образуются: только исходные вещества
        mask = (np.asarray(system.initial) > PRESENT * scale) | np.array([k == SOLVENT for k in system.kinds])
    return mask


def kind_mask(system, kind: str) -> np.ndarray:
    return np.array([k == kind for k in system.kinds])


def shift_for(solver, mask: np.ndarray) -> np.ndarray:
    return np.where(mask, 0.0, EXCLUDE_RT * R * solver.T)


def affinity_log10(solver, eq, i: int) -> float:
    """log10 насыщения частицы, вычисленный по химпотенциалам равновесия (вне этапа тоже).
    Твердое: SI. Газ: log10 равновесного парциального давления, бар."""
    return float((solver.system.A[i] @ eq.lam - solver.G[i] / (R * solver.T)) / LN10)


def in_span(system, eq, mask: np.ndarray):
    """-> f(i): строка состава частицы i - линейная комбинация присутствующих на этапе частиц.
    Только для таких частиц SI по химпотенциалам этапа имеет смысл. Иначе потенциал задают
    исключенные частицы (их следовые количества ~exp(-300)), и SI получается ложным: металлический Ba
    из BaCl2 + Na2SO4 давал SI 17,7."""
    scale = float(np.sum(np.abs(system.b))) or 1.0
    P = system.A[mask & (eq.n > PRESENT * scale)].T  # компоненты x присутствующие частицы

    def f(i: int) -> bool:
        a = system.A[i]
        if not P.size:
            return False
        x = np.linalg.lstsq(P, a, rcond=None)[0]
        return bool(np.linalg.norm(P @ x - a) < 1e-8 * (1.0 + np.linalg.norm(a)))
    return f


def supersaturated(solver, eq, mask: np.ndarray, kind: str) -> tuple[list[tuple[str, float]], bool]:
    """Частицы вида kind вне маски, которые образовались бы: SI > 0 (твердые) или p > P (газы).
    -> (пересыщенные по убыванию, есть ли кандидаты, для которых пересыщение не оценить)."""
    system = solver.system
    limit = float(np.log10(solver.P_bar)) if kind == GAS else 0.0
    ok = in_span(system, eq, mask)
    out, unknown = [], False
    for i, k in enumerate(system.kinds):
        if k != kind or mask[i]:
            continue
        if not ok(i):
            unknown = True
            continue
        a = affinity_log10(solver, eq, i)
        if a > limit:
            out.append((system.species[i].formula, round(a - limit, 2)))
    return sorted(out, key=lambda t: -t[1]), unknown


def reagents_consumed(system, eq) -> bool:
    """Ранний выход: каждый реагент израсходован (его номинальная частица < 0,1 % от исходного)."""
    from ..search.hypotheses import nominal_species_for_reagent
    for r in system.reagents:
        m = nominal_species_for_reagent(system.species, r.comp, r.phase, system.aqueous)
        if not m or r.moles <= 0:
            return False
        left = min(eq.n[i] / k for i, k in m)
        if left > 1e-3 * r.moles:
            return False
    return True


def particles(system, eq, mask: np.ndarray) -> list[dict]:
    """Этап 1: частицы после диссоциации (без растворителя и реагентов в исходной форме)."""
    scale = float(np.sum(np.abs(system.b))) or 1.0
    own = {r.comp.key for r in system.reagents}
    idx = [i for i in np.where(mask)[0] if eq.n[i] > 1e-6 * scale and system.kinds[i] != SOLVENT
           and system.species[i].key not in own]
    idx.sort(key=lambda i: -eq.n[i])
    return [{"formula": system.species[i].formula, "phase": system.species[i].phase,
             "moles": float(eq.n[i])} for i in idx[:SHOW]]


def formed(system, eq, prev_n: np.ndarray) -> list[dict]:
    """Частицы, количество которых на этапе заметно выросло (кроме растворителя)."""
    scale = float(np.sum(np.abs(system.b))) or 1.0
    d = eq.n - prev_n
    idx = [i for i in np.where(d > 1e-6 * scale)[0] if system.kinds[i] != SOLVENT]
    idx.sort(key=lambda i: -d[i])
    return [{"formula": system.species[i].formula, "phase": system.species[i].phase,
             "moles": float(eq.n[i])} for i in idx[:SHOW]]


__all__ = ["Stage", "STAGES", "DEFAULT_ORDER", "ALT_ORDER", "EXCLUDE_RT", "AQ", "COND", "GAS",
           "dissociation_mask", "kind_mask", "shift_for", "affinity_log10", "supersaturated",
           "reagents_consumed", "in_span", "particles", "formed"]
