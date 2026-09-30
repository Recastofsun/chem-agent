"""Energy source priority: user > database > (ML, DFT unavailable) > refusal."""
import pytest

from chem_agent.energy.database import get_db
from chem_agent.energy.resolver import EnergyResolver
from chem_agent.parser.formula import parse_formula
from chem_agent.thermo.gibbs import dGf_T
from tests.conftest import run


def test_db_loaded():
    db = get_db()
    assert len(db.species) > 1200
    na = db.find_formula("Na+", "aq")[0]
    assert abs(na.dGf - (-261.9)) < 0.1 and na.source == "CRC"
    w = db.find_formula("H2O", "l")[0]
    assert abs(w.dGf - (-237.1)) < 0.1


@pytest.mark.parametrize("f,ph,g", [("BaSO4", "s", -1362.2), ("CO2", "g", -394.4), ("NH4+", "aq", -79.3),
                                     ("CaCO3", "s", -1129.1), ("Fe+3", "aq", -4.7)])
def test_known_crc_values(f, ph, g):
    sp = get_db().find_formula(f, ph)[0]
    assert abs(sp.dGf - g) < 0.2


def test_manual_has_highest_priority():
    db = get_db()
    res = EnergyResolver.from_request(db, {"BaSO4": {"delta_Gf_kJ_mol": -1300.0, "phase": "s"}},
                                      [{"formula": "BaCl2", "phase": "aq"}])
    sp = res.apply(db.species, aqueous=True)
    ba = [s for s in sp if s.key == parse_formula("BaSO4").key and s.phase == "s"][0]
    assert ba.dGf == -1300.0 and ba.source.startswith("user")


def test_manual_changes_result(agent):
    """An absurdly unstable BaSO4 (user value) must stop the precipitation."""
    reag = [{"formula": "BaCl2", "moles": 0.02, "phase": "aq"}, {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}]
    base = run(agent, reag)
    assert base["products"][0]["formula"] == "BaSO4"
    r = agent.predict(reagents=reag, known_energies={"BaSO4": {"delta_Gf_kJ_mol": -1200.0, "phase": "s"}},
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    assert all(p["formula"] != "BaSO4" for p in r["products"])
    assert any(w for w in r["warnings"] if "BaSO4" in w)


def test_reagent_level_known_energy(agent):
    r = agent.predict(reagents=[{"formula": "NaOH", "moles": 0.1, "phase": "aq"},
                                {"formula": "H2SO4", "moles": 0.05, "phase": "aq",
                                 "known_energy": {"delta_Gf_kJ_mol": -690.0, "source": "user", "uncertainty": 2.0}}],
                      options={"include_uncertainty": False}).data
    eq = r["balanced_equations"][0]
    assert eq["energy_sources"]["H2SO4"].startswith("user")


def test_request_known_energies_override_reagent_level():
    db = get_db()
    res = EnergyResolver.from_request(db, {"NaCl": {"delta_Gf_kJ_mol": -380.0, "phase": "s"}},
                                      [{"formula": "NaCl", "phase": "s",
                                        "known_energy": {"delta_Gf_kJ_mol": -370.0}}])
    assert len(res.manual) == 1 and res.manual[0].dGf == -380.0


def test_unknown_species_reported(agent):
    r = run(agent, [{"formula": "Cu(NO3)2", "moles": 0.02, "phase": "s"}], temperature_K=500, solvent="none")
    assert r["status"] == "unknown"
    assert "неизвестно" in r["message"]


def test_ml_and_dft_sources_refused():
    db = get_db()
    for src in ("ml_only", "dft_only"):
        with pytest.raises(ValueError):
            EnergyResolver.from_request(db, {}, [{"formula": "NaCl"}], energy_source=src)


def test_chain_status_order():
    db = get_db()
    chain = EnergyResolver.from_request(db, {}, [{"formula": "NaCl"}]).chain_status()
    assert [c["level"] for c in chain] == [1, 2, 3, 4, 5, 6]
    assert chain[2]["available"] is False and chain[3]["available"] is False


def test_temperature_extrapolation():
    db = get_db()
    caco3 = db.find_formula("CaCO3", "s")[0]
    g500, s500, tdep = dGf_T(caco3, 500.0)
    assert tdep and g500 > caco3.dGf and s500 > caco3.sigma
