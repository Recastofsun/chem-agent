"""Uncertainty: propagation vs ensemble, calibration, determinism of the seeded ensemble."""
import math

import numpy as np

from chem_agent.uncertainty.ensemble import draws, summarize
from chem_agent.uncertainty.propagation import sigma_logK, sigma_sum


def test_sigma_sum():
    assert abs(sigma_sum([(1, 3.0), (2, 2.0)]) - 5.0) < 1e-12


def test_sigma_logK():
    assert abs(sigma_logK(5.708, 298.15) - 1.0) < 0.01


def test_draw_statistics():
    d = draws(np.array([1.0, 2.0]), 20000, 7)
    assert abs(d[:, 0].std() - 1.0) < 0.03 and abs(d[:, 1].std() - 2.0) < 0.05
    u = draws(np.array([1.0]), 20000, 7, "uniform")
    assert abs(u.std() - 1.0) < 0.03


def test_draws_seeded():
    assert np.array_equal(draws(np.ones(3), 5, 42), draws(np.ones(3), 5, 42))


def test_summary():
    s = summarize([1.0, 2.0, 3.0])
    assert s["mean"] == 2.0 and s["n"] == 3


def test_ensemble_matches_linear_propagation(agent):
    """For a fixed equation dG is linear in dGf -> ensemble std ~ propagated sigma (calibration)."""
    r = agent.predict(reagents=[{"formula": "BaCl2", "moles": 0.02, "phase": "aq"},
                                {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}],
                      options={"accuracy": "accurate", "include_kinetics": False}).data
    lin = r["balanced_equations"][0]["delta_G_uncertainty"]
    ens = r["uncertainty"]["delta_G"]["std"]
    assert abs(ens - lin) / lin < 0.35
    assert r["uncertainty"]["members"] == 64


def test_confidence_high_for_clear_case(agent):
    r = agent.predict(reagents=[{"formula": "AgNO3", "moles": 0.01, "phase": "aq"},
                                {"formula": "NaCl", "moles": 0.01, "phase": "aq"}],
                      options={"accuracy": "fast", "include_kinetics": False}).data
    assert r["summary"]["confidence"] >= 0.9


def test_contributions_sum_to_one(agent):
    r = agent.predict(reagents=[{"formula": "Zn", "moles": 0.02, "phase": "s"}, {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
                      options={"accuracy": "fast", "include_kinetics": False}).data
    c = r["uncertainty"]["contributions"]
    assert c and abs(sum(x["share"] for x in c) - 1.0) < 0.05


def test_uncertainty_grows_with_temperature(agent):
    reag = [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}]
    a = agent.predict(reagents=reag, conditions={"temperature_K": 1200, "solvent": "none"},
                      options={"accuracy": "fast", "include_kinetics": False}).data
    s298 = math.sqrt(1.0 ** 2 * 3)
    assert a["balanced_equations"][0]["delta_G_uncertainty"] > s298
