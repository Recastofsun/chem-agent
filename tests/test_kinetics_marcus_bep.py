"""W-10: Marcus и BEP - заготовки моделей барьера."""
import pytest

from chem_agent.kinetics import bep, eyring, marcus

FE_CE = [{"formula": "FeSO4", "moles": 0.001, "phase": "aq"}, {"formula": "Ce(SO4)2", "moles": 0.001, "phase": "aq"}]


def test_marcus_formula():
    assert marcus.barrier(100, 0) == pytest.approx(25.0)          # ΔG° = 0: λ/4
    assert marcus.barrier(100, -100) == pytest.approx(0.0)        # безбарьерный максимум скорости
    assert marcus.barrier(100, -200) == pytest.approx(25.0)       # инвертированная область
    assert marcus.inverted(100, -200) and not marcus.inverted(100, -50)
    assert marcus.barrier(100, -100, n_electrons=2) == pytest.approx(100 / 4 * 0.25)
    with pytest.raises(ValueError):
        marcus.barrier(0, -10)


def test_bep_formula():
    assert bep.barrier(0.5, 80, -40) == pytest.approx(60.0)
    assert bep.barrier(0.5, 10, 50) == pytest.approx(50.0)   # не ниже ΔH эндотермической реакции
    assert bep.barrier(0.9, 5, -100) == 0.0                  # не ниже нуля
    with pytest.raises(ValueError):
        bep.barrier(1.5, 10, 0)


def test_marcus_through_agent(agent):
    d = agent.predict(reagents=FE_CE, options={"include_uncertainty": False, "kinetics_model": "marcus",
                                               "kinetics": {"lambda_kJ_mol": 100.0}}).data
    k = d["kinetics"]
    dG = d["balanced_equations"][0]["delta_G_kJ_mol"]
    assert k["model"].startswith("Marcus") and k["barrier_kJ_mol"] == pytest.approx(marcus.barrier(100, dG))
    assert k["rate_constant"] == pytest.approx(eyring.rate_constant(k["barrier_kJ_mol"], 298.15))


def test_bep_through_agent(agent):
    d = agent.predict(reagents=FE_CE, options={"include_uncertainty": False, "kinetics_model": "bep",
                                               "kinetics": {"alpha": 0.5, "beta_kJ_mol": 60}}).data
    dH = d["balanced_equations"][0]["delta_H_kJ_mol"]
    assert d["kinetics"]["model"].startswith("BEP")
    assert d["kinetics"]["barrier_kJ_mol"] == pytest.approx(bep.barrier(0.5, 60, dH))


def test_missing_parameters_reported(agent):
    d = agent.predict(reagents=FE_CE, options={"include_uncertainty": False, "kinetics_model": "marcus"}).data
    assert "lambda_kJ_mol" in d["kinetics"]["note"]
