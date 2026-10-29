"""W-07: гидротермальный метод - автоклав, давление пара, каолинит при 200 °C."""
import pytest

from chem_agent.synthesis import hydrothermal as hy

OPTS = {"include_uncertainty": False, "include_kinetics": False}
GIBBSITE_QUARTZ = [{"formula": "Al(OH)3", "moles": 0.02, "phase": "s"}, {"formula": "SiO2", "moles": 0.02, "phase": "s"}]


def _run(agent, method, solvent="water", reagents=GIBBSITE_QUARTZ):
    return agent.predict(reagents=reagents, conditions={"solvent": solvent, "method": method}, options=OPTS).data


def test_kaolinite_at_200C_15bar(agent):
    assert _run(agent, None)["status"] == "no_reaction"  # aluminosilicate_lowT при 298 K
    d = _run(agent, {"type": "hydrothermal", "T_K": 473.15, "autoclave_P_bar": 15})
    assert d["status"] == "ok" and d["summary"]["main_product"] == "Al2Si2O5(OH)4"
    assert d["balanced_equations"][0]["equation"] == "2 Al(OH)3 + 2 SiO2 -> Al2Si2O5(OH)4↓ + H2O"
    assert d["system"]["T_K"] == 473.15 and d["system"]["P_bar"] == pytest.approx(15.55, abs=0.01)
    # 15 бар ниже давления пара при 200 °C: принято автогенное
    assert any("автогенное" in w for w in d["warnings"])
    assert d["synthesis"]["water_state"] == "liquid"


def test_below_kinetic_threshold(agent):
    d = _run(agent, {"type": "hydrothermal", "T_K": 398.15})
    assert d["status"] == "no_reaction" and d["system"]["P_bar"] == pytest.approx(2.32, abs=0.01)
    assert "aluminosilicate_lowT" in {f["id"] for f in d["rules_fired"]}


def test_supercritical_unreliable(agent):
    d = _run(agent, {"type": "hydrothermal", "T_K": 700})
    assert d["status"] == "unreliable" and d["synthesis"]["water_state"] == "supercritical"


@pytest.mark.parametrize("T, p", [(373.15, 1.0142), (473.15, 15.547), (573.15, 85.88)])
def test_iapws_saturation(T, p):
    assert hy.p_sat_bar(T) == pytest.approx(p, rel=2e-3)


def test_needs_water_and_temperature(agent):
    d = _run(agent, {"type": "hydrothermal", "T_K": 473.15}, solvent="none")
    assert d["status"] == "error" and "water" in d["message"]
    assert "T_K" in _run(agent, {"type": "hydrothermal"})["message"]


def test_aluminium_hydroxide_t_dependence(agent):
    # dSf гиббсита: Al(OH)3 разлагается при нагреве (раньше G(T) = G(298), разложения не было)
    d = agent.predict(reagents=[{"formula": "Al(OH)3", "moles": 0.01, "phase": "s"}],
                      conditions={"temperature_K": 800, "solvent": "none"}, options=OPTS).data
    assert d["summary"]["main_product"] == "Al2O3"
