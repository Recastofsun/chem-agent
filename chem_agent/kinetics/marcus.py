"""Теория Маркуса для внешнесферного переноса электрона (W-10, заготовка).

ΔG‡ = (λ/4)·(1 + ΔG°/λ)², ΔG° - на один перенесенный электрон (ΔG реакции / n).
λ - энергия реорганизации (внутренняя + растворитель), кДж/моль. Работа сближения ионов не учитывается.
Инвертированная область: -ΔG° > λ - барьер снова растет.
Константа скорости - по Эйрингу из ΔG‡ (адиабатический предел, κ = 1).
"""
from __future__ import annotations


def barrier(lambda_kJ_mol: float, dG_kJ_mol: float, n_electrons: int = 1) -> float:
    if lambda_kJ_mol <= 0:
        raise ValueError("lambda_kJ_mol > 0")
    dG = dG_kJ_mol / max(1, int(n_electrons))
    return lambda_kJ_mol / 4.0 * (1.0 + dG / lambda_kJ_mol) ** 2


def inverted(lambda_kJ_mol: float, dG_kJ_mol: float, n_electrons: int = 1) -> bool:
    return -dG_kJ_mol / max(1, int(n_electrons)) > lambda_kJ_mol
