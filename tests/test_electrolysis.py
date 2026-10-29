import pytest
from chem_agent.agent import Agent

OPTS = {"include_uncertainty": False, "include_kinetics": False}

@pytest.mark.parametrize("formula, voltage, expected_products", [
    # 1. Электролиз CuCl2 (1.5 В)
    ("CuCl2", 1.5, {"Cu", "Cl2"}),
    # 2. Электролиз HCl (2.0 В)
    ("HCl", 2.0, {"H2", "Cl2"}),
    # 3. Электролиз Na2SO4 (3.0 В) -> на аноде вода дает O2, на катоде H2
    ("Na2SO4", 3.0, {"H2", "O2"}),
])
def test_electrolysis_products(formula, voltage, expected_products):
    agent = Agent(offline=True)
    request = {
        "reagents": [{"formula": formula, "moles": 0.1, "phase": "aq"}],
        "conditions": {
            "temperature_K": 298.15,
            "electrolysis": {"enabled": True, "voltage_V": voltage}
        }
    }
    res = agent.predict(request=request, options=OPTS)
    data = res.data
    
    assert data["status"] in ("ok", "unreliable"), f"Ошибка статуса: {data.get('message')}"
    got_products = {p["formula"] for p in data.get("products", [])[:6]}
    assert expected_products.issubset(got_products), \
        f"Для {formula} при {voltage}В ожидались {expected_products}, но получены {got_products}"

def test_cell_mode_smoke():
    """Минимальный smoke-тест для режима двухкамерной ячейки (_run_cell)."""
    agent = Agent(offline=True)
    req = {
        "cell": {
            "anode": {
                "electrode": {"material": "Pt"},
                "solution": {"species": [{"formula": "NaCl", "moles": 0.1}]}
            },
            "cathode": {
                "electrode": {"material": "Cu"},
                "solution": {"species": [{"formula": "CuSO4", "moles": 0.1}]}
            },
            "membrane": {"type": "cation_exchange"},
            "external_circuit": {"mode": "potentiostatic", "voltage_V": 2.0}
        }
    }
    res = agent.predict(request=req)
    data = res.data
    assert data["status"] in ("ok", "error")
    if data["status"] == "ok":
        assert "cell_result" in data