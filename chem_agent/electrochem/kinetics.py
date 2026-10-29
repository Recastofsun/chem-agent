"""
Модуль электрохимической кинетики.
Реализует уравнения Нернста и Батлера-Фольмера для выбора доминирующих реакций.
"""
from __future__ import annotations

import math
from ..energy.database import get_db

F = 96485.332
R_GAS = 8.31446

def nernst_potential(e0: float, n: int, c_ox: float, c_red: float, T: float) -> float:
    """Уравнение Нернста для расчета равновесного потенциала."""
    if c_ox <= 0 or c_red <= 0:
        return e0
    return e0 - (R_GAS * T) / (n * F) * math.log(c_red / c_ox)

def select_dominant_reaction(db, U: float, concentrations: dict[str, float], T: float, side: str) -> dict | None:
    best_candidate = None
    max_current = -1.0
    
    print(f"\n--- Поиск реакции для {side} (U={U:.2f} В) ---")
    
    for (ox_f, red_f), pair in db.redox_pairs.items():
        c_ox = concentrations.get(ox_f, 0.0)
        if ox_f == "H+":
            c_ox = max(c_ox, 1e-7)
            
        c_red = concentrations.get(red_f, 0.0)
        if red_f == "OH-":
            c_red = max(c_red, 1e-7)
            
        if side == "anode" and c_red == 0.0:
            continue
        if side == "cathode" and c_ox == 0.0:
            continue
            
        e0 = pair["e0"]
        n = pair["n"]
        
        # ЧИТАЕМ ИЗ БАЗЫ ДАННЫХ
        eta_over = pair.get("overpotential_V", 0.0)
        j0 = pair.get("exchange_current_A_m2", 1e-3)
            
        E_eq = nernst_potential(e0, n, max(c_ox, 1e-6), max(c_red, 1e-6), T)
        
        if side == "anode":
            eta = U - E_eq - eta_over
        else:
            eta = U + E_eq - eta_over
            
        if eta <= 0:
            continue
            
        eta_capped = min(eta, 0.2)  # Ограничиваем экспоненту
        alpha = 0.5
        
        exponent = (alpha * n * F * eta_capped) / (R_GAS * T)
        j = j0 * math.exp(exponent)
        
        print(f"  {ox_f}/{red_f}: eta={eta:.2f}, j0={j0:.1e} -> Ток j = {j:.2e}")
        
        if j > max_current:
            max_current = j
            best_candidate = {
                "ox": ox_f, "red": red_f, "n": n, "e0": e0,
                "E_eq": E_eq, "eta": eta, "j": j
            }
            
    if best_candidate:
        print(f"  ПОБЕДИТЕЛЬ: {best_candidate['ox']}/{best_candidate['red']} (j={best_candidate['j']:.2e})")
    return best_candidate
            
    