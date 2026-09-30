"""Thermodynamics: dG, K_eq, activities, equilibrium solver."""
import math

import numpy as np
import pytest

from chem_agent.thermo.activity import dh_constants, make_gamma_fn, water_dielectric
from chem_agent.thermo.equilibrium import AQ, COND, GAS, SOLVENT, EqProblem, solve
from tests.conftest import run

R = 8.314462618e-3


def test_dh_constant_25C():
    A, B = dh_constants(298.15)
    assert abs(A - 0.509) < 0.003 and abs(B - 0.3286) < 0.002


def test_dielectric_water():
    assert abs(water_dielectric(298.15) - 78.4) < 0.3


def test_davies_value():
    f = make_gamma_fn("davies", 298.15)
    g = math.exp(f(0.1, np.array([1.0]))[0])
    assert 0.76 < g < 0.80


def test_pure_water_pH(agent):
    r = run(agent, [{"formula": "NaCl", "moles": 1e-6, "phase": "aq"}])
    assert abs(r["summary"]["pH"] - 7.0) < 0.02


def test_neutralization_pH_and_dG(agent):
    r = run(agent, [{"formula": "NaOH", "moles": 0.05, "phase": "aq"}, {"formula": "HCl", "moles": 0.05, "phase": "aq"}])
    eq = r["balanced_equations"][0]
    # H+ + OH- -> H2O: dG0 = -79.9 kJ/mol (CRC)
    assert abs(eq["delta_G_kJ_mol"] + 79.9) < 0.3
    assert abs(eq["log10_K"] - 14.0) < 0.1
    assert abs(r["summary"]["pH"] - 7.0) < 0.05


def test_acetic_acid_pH(agent):
    """0,1 M CH3COOH: pH ~ 2,88 (Ka = 1,75e-5)."""
    r = run(agent, [{"formula": "CH3COOH", "moles": 0.1, "phase": "aq"}])
    assert abs(r["summary"]["pH"] - 2.88) < 0.08


def test_ammonia_pH(agent):
    """0,1 M NH3: pH ~ 11,1."""
    r = run(agent, [{"formula": "NH3", "moles": 0.1, "phase": "aq"}])
    assert abs(r["summary"]["pH"] - 11.13) < 0.1


def test_agcl_solubility(agent):
    """AgCl Ksp ~ 1,8e-10 -> dissolved Ag ~ 1,3e-5 M."""
    r = run(agent, [{"formula": "AgCl", "moles": 0.01, "phase": "s"}], solvent="water", options={"include_uncertainty": False,
                                                                              "include_kinetics": False,
                                                                              "activity_model": "ideal"})
    ag = [c for c in r["final_composition"] if c["formula"] == "Ag+"][0]["final_mol"]
    assert 5e-6 < ag < 3e-5


def test_mass_balance_small_problem():
    # toy: 2 H2 + O2 <-> 2 H2O (gas), must conserve H and O exactly
    A = np.array([[2, 0], [0, 2], [2, 1]], float)
    g = np.array([0.0, 0.0, -228.6 / (R * 1000.0)])
    p = EqProblem(A=A, g=g, kind=[GAS, GAS, GAS], b=np.array([2.0, 1.0]), charges=np.zeros(3))
    res = solve(p)
    assert res.converged
    assert np.allclose(A.T @ res.n, [2.0, 1.0], atol=1e-9)


def test_convexity_unique_minimum_different_starts():
    A = np.array([[1, 0], [0, 1], [1, 1]], float)
    g = np.array([0.0, 0.0, -5.0])
    b = np.array([1.0, 2.0])
    r1 = solve(EqProblem(A=A, g=g, kind=[GAS, GAS, GAS], b=b, charges=np.zeros(3)))
    r2 = solve(EqProblem(A=A, g=g, kind=[GAS, GAS, GAS], b=b, charges=np.zeros(3), lam0=np.array([-3.0, -4.0])))
    assert np.allclose(r1.n, r2.n, atol=1e-8)
    # analytic: K = x/((1-x)(2-x)) * (3-x) at P=1 bar ... check equilibrium condition numerically
    nA, nB, nC = r1.n
    tot = r1.n.sum()
    assert abs(math.log((nC / tot) / ((nA / tot) * (nB / tot))) - 5.0) < 1e-6


def test_equilibrium_condition_for_solid():
    """Pure solid present -> saturation index 0."""
    A = np.array([[1.0], [1.0]])
    g = np.array([-10.0, 0.0])  # cond, gas
    res = solve(EqProblem(A=A, g=g, kind=[COND, GAS], b=np.array([1.0]), charges=np.zeros(2)))
    assert res.n[0] > 0.99


def test_caco3_decomposition_temperature(agent):
    low = run(agent, [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}], temperature_K=800, solvent="none")
    high = run(agent, [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}], temperature_K=1300, solvent="none")
    assert low["status"] == "no_reaction"
    assert high["status"] == "ok" and high["products"][0]["formula"] in ("CaO", "CO2")


def test_solvent_species_kinds():
    assert {AQ, COND, GAS, SOLVENT} == {"aq", "cond", "g", "solvent"}
