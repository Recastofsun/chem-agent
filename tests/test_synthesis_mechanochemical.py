"""W-08: механохимический метод - вспышечная температура удара шаров (CaCO3 + SiO2 -> CaSiO3 без растворителя)."""
import pytest

from chem_agent.synthesis import mechanochemical as me

OPTS = {"include_uncertainty": False, "include_kinetics": False}
CACO3_SIO2 = [{"formula": "CaCO3", "moles": 0.01, "phase": "s"}, {"formula": "SiO2", "moles": 0.01, "phase": "s"}]


def _run(agent, method, solvent="none"):
    return agent.predict(reagents=CACO3_SIO2, conditions={"solvent": solvent, "method": method}, options=OPTS).data


def test_wollastonite_by_ball_milling(agent):
    assert _run(agent, None)["status"] == "no_reaction"
    d = _run(agent, {"type": "mechanochemical", "rpm": 600, "ball_material": "steel"})
    assert d["status"] == "ok" and d["summary"]["main_product"] == "CaSiO3"
    assert d["balanced_equations"][0]["equation"] == "CaCO3 + SiO2 -> CaSiO3 + CO2↑"
    s = d["synthesis"]
    assert s["used"] == "zone" and s["zone_T_K"] == pytest.approx(298.15 + 440, abs=1)


def test_slow_mill_no_reaction(agent):
    d = _run(agent, {"type": "mechanochemical", "rpm": 200})
    assert d["status"] == "no_reaction" and d["synthesis"]["used"] == "bulk"


def test_heavy_balls_hotter():
    # при равной скорости карбид вольфрама (15,6 г/см3) греет зону сильнее агата (2,65)
    assert me.flash_dT(400, "tungsten_carbide") > 2 * me.flash_dT(400, "agate")
    assert me.flash_dT(400, "steel", wet=True) == pytest.approx(0.5 * me.flash_dT(400, "steel"))
    assert me.ball_velocity(600, 0.1) == pytest.approx(3.14, abs=0.01)


def test_material_affects_result(agent):
    wc = _run(agent, {"type": "mechanochemical", "rpm": 400, "ball_material": "tungsten_carbide"})
    agate = _run(agent, {"type": "mechanochemical", "rpm": 400, "ball_material": "agate"})
    assert wc["summary"]["main_product"] == "CaSiO3" and agate["status"] == "no_reaction"
    assert any("примесь SiO2" in w for w in agate["warnings"])


@pytest.mark.parametrize("method, msg", [
    ({"type": "mechanochemical"}, "rpm"),
    ({"type": "mechanochemical", "rpm": 500, "ball_material": "wood"}, "ball_material"),
])
def test_validation(agent, method, msg):
    d = _run(agent, method)
    assert d["status"] == "error" and msg in d["message"]
