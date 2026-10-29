"""W-14: модель Pitzer (Harvie-Moller-Weare 1984)."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

from chem_agent.agent import Agent
from chem_agent.energy.database import get_db
from chem_agent.thermo.activity import dh_constants, make_gamma_fn


def _gamma_pm(cation, z_c, anion, z_a, m):
    """Средний ионный коэффициент активности соли 1:1 или 2:2 при моляльности m."""
    sp = [SimpleNamespace(formula=cation, charge=z_c), SimpleNamespace(formula=anion, charge=z_a)]
    f = make_gamma_fn("pitzer", 298.15, species_list=sp, db=get_db())
    lng = f(0.0, np.array([z_c, z_a]), m=np.array([m, m]))
    return math.exp(lng.mean())


def test_db_has_pitzer_parameters():
    p = get_db().get_pitzer("SO4-2", "Ca+2")
    assert p and p["beta2"] == pytest.approx(-54.24)
    assert get_db().get_pitzer("Na+", "Cl-")["beta0"] == pytest.approx(0.0765)


@pytest.mark.parametrize("m, expected", [(0.1, 0.778), (1.0, 0.657), (3.0, 0.714)])
def test_nacl_mean_gamma(m, expected):
    # Robinson & Stokes, 25 C
    assert _gamma_pm("Na+", 1, "Cl-", -1, m) == pytest.approx(expected, abs=0.005)


def test_caso4_gamma_at_saturation():
    # HMW1984: gamma(CaSO4) = 0.336 при m = 0.0152 (насыщение по гипсу)
    assert _gamma_pm("Ca+2", 2, "SO4-2", -2, 0.0152) == pytest.approx(0.336, abs=0.005)


def test_pitzer_dilute_limit_matches_debye_huckel():
    A, _ = dh_constants(298.15)
    m = 1e-5
    g = _gamma_pm("Na+", 1, "Cl-", -1, m)
    assert math.log10(g) == pytest.approx(-A * math.sqrt(m), rel=0.01)


def test_unknown_pair_gives_dh_only():
    sp = [SimpleNamespace(formula="Zz+", charge=1), SimpleNamespace(formula="Qq-", charge=-1),
          SimpleNamespace(formula="CO2", charge=0)]
    f = make_gamma_fn("pitzer", 298.15, species_list=sp, db=get_db())
    lng = f(0.0, np.array([1, -1, 0]), m=np.array([0.1, 0.1, 0.05]))
    assert lng[2] == 0.0 and lng[0] == pytest.approx(lng[1]) and lng[0] < 0


def test_gypsum_solubility_phreeqc_01():
    req = {"reagents": [{"formula": "CaSO4", "moles": 1.0, "phase": "s"}],
           "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}}
    data = Agent(offline=True).predict(request=req).data
    assert data["status"] == "ok"
    fc = {(p["formula"], p["phase"]): p["final_mol"] for p in data["final_composition"]}
    water_kg = fc[("H2O", "l")] * 0.018015268
    assert fc[("Ca+2", "aq")] / water_kg == pytest.approx(0.0152, rel=0.02)
    assert data["summary"]["main_product"] == "CaSO4·2H2O"
