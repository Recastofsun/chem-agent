"""
Обертка для решения электрохимических задач.
Использует fixed_lambda и накладывает штраф за перенапряжение.
"""
from __future__ import annotations

import numpy as np
from .equilibrium import EqProblem, solve
from ..energy.database import get_db

F = 96485.332
R_GAS = 8.31446

def solve_kkt(A, b, g0, charges, phi, T, kinds, charge_col=None, gamma_fn=None, max_iter=200, n0=None, species_list=None):
    db = get_db()
    g_eff = g0.copy()
    
    # 1. Системный учет перенапряжения (штрафуем ПРОДУКТЫ реакции)
    if species_list is not None and abs(phi) > 1e-6:
        for i, s in enumerate(species_list):
            for (ox_f, red_f), pair in db.redox_pairs.items():
                eta = pair.get("overpotential_V", 0.0)
                e0 = pair["e0"]
                
                # Если мы на аноде (phi < 0) и это продукт окисления
                if phi < 0 and s.formula == ox_f:
                    if abs(phi) < (e0 + eta):
                        # Если напряжения не хватает, жестко блокируем продукт
                        g_eff[i] += 100.0 
                # Если мы на катоде (phi > 0) и это продукт восстановления
                elif phi > 0 and s.formula == red_f:
                    if abs(phi) < (e0 + eta):
                        g_eff[i] += 100.0

    # 2. Формируем fixed_lambda для электрохимического сдвига
    fixed_lambda = None
    if abs(phi) > 1e-6 and charge_col is not None:
        fixed_lambda = {charge_col: -F * phi / (R_GAS * T)}
    
    p = EqProblem(
        A=A, g=g_eff, kind=kinds, b=b, charges=charges,
        P_bar=1.0, gamma_fn=gamma_fn, charge_col=charge_col,
        fixed_lambda=fixed_lambda
    )
    
    try:
        res = solve(p, max_outer=max_iter)
        return res.n, res.lam, res.converged
    except Exception as e:
        print(f"Ошибка решателя: {e}")
        return None, None, False