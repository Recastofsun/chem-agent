"""
Обертка для решения электрохимических задач.
Использует двойственный решатель (Barrier Method) из equilibrium.py.
"""
from __future__ import annotations

import numpy as np
from .equilibrium import EqProblem, solve

F = 96485.332
R_GAS = 8.31446

def solve_kkt(A, b, g0, charges, phi, T, kinds, charge_col=None, gamma_fn=None, max_iter=200, n0=None):
    # 1. Сдвигаем химические потенциалы на величину z * F * phi / RT
    g_eff = g0 + (charges * F * phi) / (R_GAS * T)
    
    # 2. Создаем задачу (без фиксации лямбды, так как заряд уже удален из A)
    p = EqProblem(
        A=A,
        g=g_eff,
        kind=kinds,
        b=b,
        charges=charges,
        P_bar=1.0,
        gamma_fn=gamma_fn,
        charge_col=None  # Заряд отключен
    )
    
    # 3. Запускаем двойственный решатель
    try:
        res = solve(p, max_outer=max_iter)
        return res.n, res.lam, res.converged
    except Exception as e:
        print(f"Ошибка решателя: {e}")
        return None, None, False