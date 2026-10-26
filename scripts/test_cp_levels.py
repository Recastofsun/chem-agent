"""Проверка трёх уровней T-зависимости в dGf_T: Cp, Ulich, константа."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chem_agent.energy.database import get_db, Species
from chem_agent.thermo.gibbs import dGf_T, T0, _cp_correction


def main():
    db = get_db()
    T = 1000.0

    # 1. Cp + dSf (полная интеграция)
    sp_cp = next(s for s in db.species if s.formula == "CaCO3" and s.phase == "s" and s.dGf is not None)
    g_cp, sig_cp, tdep_cp = dGf_T(sp_cp, T)
    print(f"[Cp]    CaCO3: Gf({T}) = {g_cp:.2f} кДж/моль, tdep={tdep_cp}")

    # 2. Ulich (только dSf) — создаём копию без Cp
    sp_ulich = Species(
        formula=sp_cp.formula, phase=sp_cp.phase, elements=sp_cp.elements, charge=sp_cp.charge,
        dGf=sp_cp.dGf, dHf=sp_cp.dHf, S=sp_cp.S, Cp=None, dSf=sp_cp.dSf,
        source=sp_cp.source, sigma=sp_cp.sigma,
    )
    g_ulich, sig_ulich, tdep_ulich = dGf_T(sp_ulich, T)
    print(f"[Ulich] CaCO3: Gf({T}) = {g_ulich:.2f} кДж/моль, tdep={tdep_ulich}")

    # 3. Константа (нет dSf, нет Cp)
    sp_const = Species(
        formula=sp_cp.formula, phase=sp_cp.phase, elements=sp_cp.elements, charge=sp_cp.charge,
        dGf=sp_cp.dGf, dHf=sp_cp.dHf, S=sp_cp.S, Cp=None, dSf=None,
        source=sp_cp.source, sigma=sp_cp.sigma,
    )
    g_const, sig_const, tdep_const = dGf_T(sp_const, T)
    print(f"[Const] CaCO3: Gf({T}) = {g_const:.2f} кДж/моль, tdep={tdep_const}")

    # Проверки
    print()
    print("=== ПРОВЕРКИ ===")
    assert tdep_cp is True, "Cp: tdep должен быть True"
    assert tdep_ulich is True, "Ulich: tdep должен быть True"
    assert tdep_const is False, "Const: tdep должен быть False"
    assert abs(g_cp - g_ulich) > 1.0, "Cp и Ulich должны отличаться"
    assert abs(g_ulich - g_const) > 1.0, "Ulich и Const должны отличаться"

    # Проверка T=298.15 (все уровни дают одно и то же)
    g_cp_298, _, _ = dGf_T(sp_cp, T0)
    g_ulich_298, _, _ = dGf_T(sp_ulich, T0)
    g_const_298, _, _ = dGf_T(sp_const, T0)
    print(f"При T=298.15 K: Cp={g_cp_298:.2f}, Ulich={g_ulich_298:.2f}, Const={g_const_298:.2f}")
    assert abs(g_cp_298 - g_ulich_298) < 1e-9, "При 298.15 K Cp и Ulich должны совпадать"
    assert abs(g_ulich_298 - g_const_298) < 1e-9, "При 298.15 K Ulich и Const должны совпадать"

    print("✅ Все проверки пройдены")


if __name__ == "__main__":
    main()