"""Сравнение Ulich и Cp-интеграции при высоких T (W-02)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from chem_agent.energy.database import get_db
from chem_agent.thermo.gibbs import dGf_T, T0


def ulich_g(sp, T):
    """Ulich без Cp: Gf(T) = Gf(298) - (T-298)*dSf/1000."""
    if sp.dSf is None:
        return sp.dGf
    return sp.dGf - (T - T0) * sp.dSf / 1000.0


def main():
    db = get_db()
    T = 1200.0

    print(f"{'Вещество':<12} | {'Cp':<8} | {'Gf(298)':<10} | {'Ulich(1200)':<12} | {'Cp(1200)':<10} | {'Δ (Cp-Ulich)':<12}")
    print("-" * 90)

    g_ulich_sum = 0.0
    g_cp_sum = 0.0

    for formula, phase in [("CaCO3", "s"), ("CaO", "s"), ("CO2", "g")]:
        sp_list = [s for s in db.species if s.formula == formula and s.phase == phase and s.dGf is not None]
        if not sp_list:
            print(f"⚠️  {formula}({phase}) не найден")
            continue
        sp = sp_list[0]

        g_ulich = ulich_g(sp, T)
        g_cp, _, _ = dGf_T(sp, T)
        delta = g_cp - g_ulich

        print(
            f"{formula}({phase}){'':<2} | {sp.Cp or '—':<8} | {sp.dGf:<10.2f} | "
            f"{g_ulich:<12.2f} | {g_cp:<10.2f} | {delta:<+12.2f}"
        )

        # Для реакции CaCO3 -> CaO + CO2: реагент с плюсом, продукты с минусом
        if formula == "CaCO3":
            g_ulich_sum += g_ulich
            g_cp_sum += g_cp
        else:
            g_ulich_sum -= g_ulich
            g_cp_sum -= g_cp

    print()
    print(f"ΔG(1200 K) для CaCO3 → CaO + CO2:")
    print(f"  Ulich: {g_ulich_sum:+.2f} кДж/моль")
    print(f"  Cp:    {g_cp_sum:+.2f} кДж/моль")
    print(f"  Разница: {g_cp_sum - g_ulich_sum:+.2f} кДж/моль")


if __name__ == "__main__":
    main()