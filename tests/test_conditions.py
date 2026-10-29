"""Influence of T, P, pH, ionic strength, dielectric constant, atmosphere, catalyst."""
from chem_agent.conditions.ph import titrant_for_initial_pH
from chem_agent.conditions.temperature import profile_points
from tests.conftest import run

OPTS = {"include_uncertainty": False, "include_kinetics": False}


def test_temperature_changes_equilibrium(agent):
    a = run(agent, [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}], temperature_K=1000, solvent="none")
    b = run(agent, [{"formula": "CaCO3", "moles": 0.1, "phase": "s"}], temperature_K=1300, solvent="none")
    ca = sum(p["moles"] for p in a["products"] if p["formula"] == "CaO")
    cb = sum(p["moles"] for p in b["products"] if p["formula"] == "CaO")
    assert cb > ca


def test_pressure_le_chatelier(agent):
    """N2 + 3H2 <-> 2NH3: higher pressure -> more NH3."""
    reag = [{"formula": "N2", "moles": 1.0, "phase": "g"}, {"formula": "H2", "moles": 3.0, "phase": "g"}]
    lo = run(agent, reag, temperature_K=700, pressure_atm=1, solvent="none")
    hi = run(agent, reag, temperature_K=700, pressure_atm=200, solvent="none")
    n_lo = sum(p["moles"] for p in lo["products"] if p["formula"] == "NH3")
    n_hi = sum(p["moles"] for p in hi["products"] if p["formula"] == "NH3")
    assert n_hi > 5 * max(n_lo, 1e-9)


def test_initial_pH(agent):
    r = agent.predict(reagents=[{"formula": "NaCl", "moles": 1e-4, "phase": "aq"}],
                      conditions={"pH": {"initial": 3.0}}, options=OPTS).data
    assert abs(r["summary"]["pH"] - 3.0) < 0.05


def test_buffered_pH(agent):
    r = agent.predict(reagents=[{"formula": "CH3COOH", "moles": 0.05, "phase": "aq"}],
                      conditions={"pH": {"initial": 5.0, "buffered": True}}, options=OPTS).data
    assert abs(r["summary"]["pH"] - 5.0) < 0.01


def test_titrant_calc():
    assert titrant_for_initial_pH(2.0, 1.0)[0] == "HCl"
    assert titrant_for_initial_pH(12.0, 1.0)[0] == "NaOH"
    assert titrant_for_initial_pH(7.0, 1.0) is None


def test_ionic_strength_override(agent):
    reag = [{"formula": "CH3COOH", "moles": 0.01, "phase": "aq"}]
    a = agent.predict(reagents=reag, options=OPTS).data
    b = agent.predict(reagents=reag, conditions={"solvent": {"name": "water", "ionic_strength_M": 1.0,
                                                              "activity_model": "davies"}}, options=OPTS).data
    assert b["summary"]["ionic_strength_M"] == 1.0

    def acetate(d):
        return sum(c["final_mol"] for c in d["final_composition"] if c["formula"] == "CH3COO-")
    assert acetate(b) > 1.1 * acetate(a)  # lower gamma -> more dissociation


def test_dielectric_override_changes_activity(agent):
    reag = [{"formula": "CH3COOH", "moles": 0.01, "phase": "aq"}, {"formula": "NaCl", "moles": 0.2, "phase": "aq"}]
    a = agent.predict(reagents=reag, options=OPTS).data
    b = agent.predict(reagents=reag, conditions={"solvent": {"name": "water", "dielectric_constant": 40.0}},
                      options=OPTS).data
    def acetate(d):
        return sum(c["final_mol"] for c in d["final_composition"] if c["formula"] == "CH3COO-")
    assert acetate(b) > 1.05 * acetate(a)  # lower dielectric constant -> stronger ionic interaction


def test_activity_model_ideal_vs_dh(agent):
    reag = [{"formula": "CH3COOH", "moles": 0.01, "phase": "aq"}, {"formula": "NaCl", "moles": 0.1, "phase": "aq"}]
    a = agent.predict(reagents=reag, options={**OPTS, "activity_model": "ideal"}).data
    b = agent.predict(reagents=reag, options={**OPTS, "activity_model": "davies"}).data
    assert a["summary"]["pH"] != b["summary"]["pH"]


def test_atmosphere_co2_acidifies_water(agent):
    r = agent.predict(reagents=[{"formula": "NaCl", "moles": 1e-5, "phase": "aq"}],
                      conditions={"atmosphere": {"composition": {"N2": 0.78, "O2": 0.21, "CO2": 0.0004},
                                                 "mode": "open"}}, options=OPTS).data
    assert 5.4 < r["summary"]["pH"] < 5.8  # pure water in air: pH ~ 5,6


def test_atmosphere_o2_oxidizes_ferrous(agent):
    r = agent.predict(reagents=[{"formula": "FeSO4", "moles": 0.001, "phase": "aq"}, {"formula": "NaOH", "moles": 0.002, "phase": "aq"}],
                      conditions={"atmosphere": {"composition": {"N2": 0.79, "O2": 0.21}, "mode": "open"}},
                      options=OPTS).data
    assert r["products"][0]["formula"] == "Fe(OH)3"


def test_catalyst_does_not_change_equilibrium(agent):
    reag = [{"formula": "N2", "moles": 1.0, "phase": "g"}, {"formula": "H2", "moles": 3.0, "phase": "g"}]
    a = agent.predict(reagents=reag, conditions={"temperature_K": 700, "solvent": "none"}, options=OPTS).data
    b = agent.predict(reagents=reag, conditions={"temperature_K": 700, "solvent": "none",
                                                 "catalyst": {"formula": "Fe", "barrier_kJ_mol": 80}},
                      options={**OPTS, "include_kinetics": True}).data
    assert [p["moles"] for p in a["products"]] == [p["moles"] for p in b["products"]]
    assert b["kinetics"]["rate_constant"] is not None


def test_ramp_profile_points():
    pts = profile_points({"temperature_K": 298.15, "time": {"sample_points": 5},
                          "temperature_profile": {"type": "ramp", "start_K": 300, "end_K": 400, "rate_K_per_min": 5}})
    assert len(pts) == 5 and pts[-1]["T_K"] == 400 and abs(pts[-1]["t_s"] - 1200) < 1e-6


def test_forbid_unsupported_solvent(agent):
    import pytest
    # с v2.3 Agent.predict возвращает status=error вместо исключения ValidationError
    r = agent.predict(reagents=[{"formula": "NaCl", "moles": 1}], conditions={"solvent": "benzene"}).data
    assert r["status"] == "error" and "benzene" in r["message"]
