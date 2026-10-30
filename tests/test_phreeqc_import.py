import pytest
from chem_agent.agent import Agent

@pytest.fixture
def agent_phreeqc():
    return Agent(offline=True, db_path='chem_agent/data/phreeqc.db')

def test_phreeqc_calcite_physics(agent_phreeqc):
    """Проверка электронейтральности и pH для кальцита."""
    req = {
        "reagents": [{"formula": "CaCO3", "moles": 1.0, "phase": "s"}],
        "conditions": {
            "temperature_K": 298.15, 
            "solvent": {"name": "water"}, 
            "volume_L": 1.0,
            "atmosphere": {"mode": "fixed", "composition": {"CO2": 3.16e-4}}
        },
        "options": {"include_uncertainty": False, "include_kinetics": False}
    }
    res = agent_phreeqc.predict(request=req)
    data = res.data
    assert 8.0 < data["summary"]["pH"] < 8.5
    comp = {p["formula"]: p["final_mol"] for p in data["final_composition"] if p["phase"] == "aq"}
    assert 0.0001 < comp.get("Ca+2", 0) < 0.001

def test_phreeqc_gypsum_solubility(agent_phreeqc):
    """Проверка растворимости гипса (должна быть около 0.0152 М)."""
    req = {
        "reagents": [{"formula": "CaSO4·2H2O", "moles": 1.0, "phase": "s"}],
        "conditions": {"temperature_K": 298.15, "solvent": {"name": "water"}, "volume_L": 1.0},
        "options": {"include_uncertainty": False}
    }
    res = agent_phreeqc.predict(request=req)
    data = res.data
    comp = {p["formula"]: p["final_mol"] for p in data["final_composition"] if p["phase"] == "aq"}
    assert 0.010 < comp.get("SO4-2", 0) < 0.020

def test_phreeqc_barite_precipitation(agent_phreeqc):
    """Проверка импортированного комплекса BaSO4(aq) и минерала BaSO4(s)."""
    req = {
        "reagents": [
            {"formula": "BaCl2", "moles": 0.01, "phase": "aq"},
            {"formula": "Na2SO4", "moles": 0.01, "phase": "aq"}
        ],
        "conditions": {"temperature_K": 298.15, "solvent": {"name": "water"}, "volume_L": 2.0},
        "options": {"include_uncertainty": False}
    }
    res = agent_phreeqc.predict(request=req)
    data = res.data
    
    comp = {p["formula"]: p["final_mol"] for p in data["final_composition"]}
    # Барит должен выпасть в осадок (около 0.01 моль)
    assert comp.get("BaSO4", 0) > 0.009
    # Ион бария в растворе должен быть очень мал (из-за Ksp и комплекса)
    assert comp.get("Ba+2", 0) < 1e-4

def test_phreeqc_new_complexes_are_present(agent_phreeqc):
    """Проверка, что новые импортированные комплексы реально есть в базе."""
    db = agent_phreeqc.db
    # Проверяем наличие CaHCO3+ и BaSO4(aq)
    assert any(s.formula == "CaHCO3+" and s.phase == "aq" for s in db.species)
    assert any(s.formula == "BaSO4" and s.phase == "aq" for s in db.species)