"""W-06: сонохимический метод - горячие точки кавитации и закалка (CaCO3 + SiO2 -> CaSiO3 + CO2 при 20 кГц)."""
import pytest

from chem_agent.synthesis import sonochemical as so

OPTS = {"include_uncertainty": False, "include_kinetics": False}
CACO3_SIO2 = [{"formula": "CaCO3", "moles": 0.01, "phase": "s"}, {"formula": "SiO2", "moles": 0.01, "phase": "s"}]


def _run(agent, method, solvent="water", reagents=CACO3_SIO2):
    return agent.predict(reagents=reagents, conditions={"solvent": solvent, "method": method}, options=OPTS).data


def test_wollastonite_at_20_khz(agent):
    assert _run(agent, None)["status"] == "no_reaction"  # при 298 K ΔG = +41 кДж/моль
    d = _run(agent, {"type": "sonochemical", "frequency_kHz": 20, "power_W": 100})
    assert d["status"] == "ok" and d["summary"]["main_product"] == "CaSiO3"
    assert d["balanced_equations"][0]["equation"] == "CaCO3 + SiO2 -> CaSiO3 + CO2↑"
    s = d["synthesis"]
    assert s["cavitation"] and s["used"] == "zone" and s["bulk_result"]["status"] == "no_reaction"
    assert any("Неравновесный результат" in w for w in d["warnings"])
    assert d["input"]["conditions"]["temperature_K"] == 298.15  # вход - исходный, не зона


@pytest.mark.parametrize("method, solvent, reason", [
    ({"type": "sonochemical", "frequency_kHz": 20}, "none", "нет жидкости"),
    ({"type": "sonochemical", "frequency_kHz": 5000}, "water", "не успевают вырасти"),
    ({"type": "sonochemical", "frequency_kHz": 10}, "water", "слышимый звук"),
    ({"type": "sonochemical", "frequency_kHz": 20, "power_W": 0.001, "horn_area_cm2": 100}, "water", "порог Блейка"),
])
def test_no_cavitation(agent, method, solvent, reason):
    d = _run(agent, method, solvent)
    assert d["status"] == "no_reaction" and not d["synthesis"]["cavitation"]
    assert any(reason in w for w in d["warnings"])


def test_same_reaction_in_bulk_keeps_bulk(agent):
    # реакция в растворе идет и без ультразвука: итог - объем
    r = [{"formula": "BaCl2", "moles": 0.01, "phase": "aq"}, {"formula": "Na2SO4", "moles": 0.01, "phase": "aq"}]
    d = _run(agent, {"type": "sonochemical", "frequency_kHz": 35}, reagents=r)
    assert d["summary"]["main_product"] == "BaSO4" and d["synthesis"].get("used") is None


def test_pressure_amplitude():
    # 100 Вт на 1 см2: I = 1e6 Вт/м2, P_a = sqrt(2·1000·1482·1e6) = 17,2 бар
    assert so.pressure_amplitude_bar(100, 1) == pytest.approx(17.22, abs=0.01)


def test_requires_frequency(agent):
    d = _run(agent, {"type": "sonochemical"})
    assert d["status"] == "error" and "frequency_kHz" in d["message"]
