"""W-00: атмосфера над раствором (нормировка долей, режим fixed, давление открытой системы)."""
import pytest

from chem_agent.search.hypotheses import headspace_gas

OPTS = {"include_uncertainty": False, "include_kinetics": False}


def test_partial_composition_not_renormalized():
    # {"CO2": 3.16e-4} - мольная доля, остаток балластный N2, а не чистый CO2
    g = headspace_gas({"composition": {"CO2": 3.16e-4}}, 1000.0, 1.0, 298.15)
    assert g["CO2"] / (g["CO2"] + g["N2"]) == pytest.approx(3.16e-4)


def test_full_composition_unchanged():
    g = headspace_gas({"composition": {"N2": 0.79, "O2": 0.21}}, 1000.0, 1.0, 298.15)
    assert g["O2"] / (g["N2"] + g["O2"]) == pytest.approx(0.21)


def test_calcite_fixed_pco2(agent):
    # Кальцит при pCO2 = 10^-3.5 атм, 25 C: pH 8.3, Ca ~0.5 ммоль/кг (Plummer & Busenberg 1982)
    d = agent.predict(reagents=[{"formula": "CaCO3", "moles": 1.0, "phase": "s"}],
                      conditions={"solvent": "water", "volume_L": 1.0,
                                  "atmosphere": {"mode": "fixed", "composition": {"CO2": 0.000316}}},
                      options=OPTS).data
    ca = next(p["final_mol"] for p in d["final_composition"] if p["formula"] == "Ca+2")
    assert d["summary"]["pH"] == pytest.approx(8.3, abs=0.1)
    assert ca == pytest.approx(5.0e-4, rel=0.15)


def test_dry_open_decomposition_still_releases_o2(agent):
    # Сухая открытая система: газы-продукты уходят, KNO3 -> KNO2 при 700 K (h054)
    d = agent.predict(reagents=[{"formula": "KNO3", "moles": 0.1, "phase": "s"}],
                      conditions={"temperature_K": 700.0, "solvent": "none",
                                  "atmosphere": {"mode": "open", "headspace_L": 1000.0,
                                                 "composition": {"N2": 0.78, "O2": 0.21}}},
                      options=OPTS).data
    assert d["summary"]["main_product"] == "KNO2"
