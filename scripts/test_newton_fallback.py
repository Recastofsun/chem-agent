"""Проверка W-01: Newton с Якобианом (env-флаги)."""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import time
from chem_agent.energy.database import get_db
from chem_agent.thermo.equilibrium import EqProblem, solve
from chem_agent.thermo.gibbs import R, dGf_T
from chem_agent.thermo.activity import make_gamma_fn
from chem_agent.search.hypotheses import build_system, Reagent
from chem_agent.search.rules import RuleOutcome
from chem_agent.parser.formula import parse_formula


def run_case(name, reagents_list, model):
    db = get_db()
    T = 298.15
    reagents = [Reagent(f, parse_formula(f), m, ph) for f, m, ph in reagents_list]
    sys_ch = build_system(db.species, reagents, T=T, P_bar=1.0, aqueous=True,
                          water_kg=1.0, rules=RuleOutcome())
    if not sys_ch.species:
        print(f"[{name}] Пустая система")
        return

    g0 = np.array([dGf_T(s, T)[0] / (R * T) for s in sys_ch.species])
    charges = np.array([s.charge for s in sys_ch.species])
    aq_species = [s for s in sys_ch.species if s.phase == "aq"]
    gamma_fn = make_gamma_fn(model, T, species_list=aq_species, db=db)

    p = EqProblem(A=sys_ch.A, g=g0, kind=sys_ch.kinds, b=sys_ch.b, charges=charges,
                  P_bar=1.0, gamma_fn=gamma_fn, charge_col=sys_ch.charge_col)

    t0 = time.time()
    res = solve(p, max_outer=40, newton_threshold=12)
    dt = time.time() - t0

    print(f"\n[{name}]")
    print(f"  Converged: {res.converged}")
    print(f"  Time: {dt:.3f} s")
    print(f"  Ionic strength: {res.ionic_strength:.4f} M")
    print(f"  Messages:")
    for m in res.messages:
        print(f"    {m}")


if __name__ == "__main__":
    # Тест 1: чистый Anderson (env-переменных нет)
    os.environ.pop("CHEM_AGENT_DEBUG_FORCE_NEWTON_AFTER", None)
    os.environ.pop("CHEM_AGENT_DEBUG_DISABLE_ANDERSON", None)
    print("=" * 60)
    print("ТЕСТ 1: 3 M FeCl3 — Anderson (production)")
    print("=" * 60)
    run_case("3 M FeCl3 (Anderson)",
             [("FeCl3", 3.0, "aq"), ("H2O", 55.5, "l")], "sit")

    # Тест 2: форсировать Newton после 1 итерации Anderson (warm start)
    os.environ["CHEM_AGENT_DEBUG_FORCE_NEWTON_AFTER"] = "1"
    print("\n" + "=" * 60)
    print("ТЕСТ 2: 3 M FeCl3 — 1 Anderson → Newton")
    print("=" * 60)
    run_case("3 M FeCl3 (1 Anderson → Newton)",
             [("FeCl3", 3.0, "aq"), ("H2O", 55.5, "l")], "sit")

    # Тест 3: чистый Newton без Anderson (проверка, что он не сломается)
    os.environ.pop("CHEM_AGENT_DEBUG_FORCE_NEWTON_AFTER", None)
    os.environ["CHEM_AGENT_DEBUG_DISABLE_ANDERSON"] = "1"
    print("\n" + "=" * 60)
    print("ТЕСТ 3: 3 M FeCl3 — только Newton (disable_anderson)")
    print("=" * 60)
    run_case("3 M FeCl3 (Newton only)",
             [("FeCl3", 3.0, "aq"), ("H2O", 55.5, "l")], "sit")

    # Сброс env для последующих запусков
    os.environ.pop("CHEM_AGENT_DEBUG_DISABLE_ANDERSON", None)