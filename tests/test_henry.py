"""W-11: henry_constants - таблица, Вант-Гофф, согласие с ΔGf базы, растворенные формы газов."""
import math

import pytest

from chem_agent.energy.database import get_db

R = 8.314462618e-3


def _kh_db(gas):
    db = get_db()
    g, a = db.find_formula(gas, "g")[0], db.find_formula(gas, "aq")[0]
    return math.exp(-(a.dGf - g.dGf) / (R * 298.15))


def test_table_loaded():
    db = get_db()
    assert len(db.henry_constants) == 17
    assert db.get_henry("CO2") == pytest.approx(3.4e-2 / 1.01325, rel=1e-9)
    assert db.get_henry("XeF6") is None


def test_vant_hoff_temperature():
    db = get_db()
    # растворимость газа падает с ростом T; CO2 при 333 K: exp(2400·(1/333,15 - 1/298,15)) = 0,43
    assert db.get_henry("CO2", 333.15) / db.get_henry("CO2") == pytest.approx(0.430, abs=0.005)


@pytest.mark.parametrize("gas, tol", [("O2", 0.1), ("CO2", 0.1), ("NH3", 0.1), ("H2S", 0.1), ("SO2", 0.1)])
def test_consistent_with_db_energies(gas, tol):
    assert _kh_db(gas) == pytest.approx(get_db().get_henry(gas), rel=tol)


@pytest.mark.parametrize("gas", ["CH4", "CO", "NO", "Ar"])
def test_dissolved_forms_added(gas):
    # aq-формы, которых не было: построены из газа и kH, обратный пересчет дает kH
    assert _kh_db(gas) == pytest.approx(get_db().get_henry(gas), rel=1e-3)


def test_methane_dissolves(agent):
    d = agent.predict(reagents=[{"formula": "CH4", "moles": 1e-4, "phase": "g"}],
                      conditions={"solvent": "water", "volume_L": 1.0},
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    aq = [c for c in d["final_composition"] if c["formula"] == "CH4" and c["phase"] == "aq"]
    assert aq and aq[0]["final_mol"] > 0
