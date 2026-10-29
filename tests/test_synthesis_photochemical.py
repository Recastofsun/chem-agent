"""W-05: фотохимический метод - свет как инициатор цепи (H2 + Cl2 -> 2 HCl под светом)."""
import pytest

from chem_agent.synthesis import photochemical as ph

OPTS = {"include_uncertainty": False, "include_kinetics": False}
H2_CL2 = [{"formula": "H2", "moles": 0.1, "phase": "g"}, {"formula": "Cl2", "moles": 0.1, "phase": "g"}]


def _run(agent, reagents, method):
    return agent.predict(reagents=reagents, conditions={"solvent": "none", "method": method}, options=OPTS).data


def test_h2_cl2_under_light(agent):
    dark = _run(agent, H2_CL2, None)
    assert dark["status"] == "no_reaction"
    d = _run(agent, H2_CL2, {"type": "photochemical", "wavelength_nm": 450, "intensity": 1.0})
    assert d["status"] == "ok" and d["summary"]["main_product"] == "HCl"
    assert d["balanced_equations"][0]["equation"] == "H2 + Cl2 -> 2 HCl↑"
    assert "gas_mix_no_igniter" not in {f["id"] for f in d["rules_fired"]}
    s = d["synthesis"]
    assert s["initiated"] and s["absorbers"][0]["formula"] == "Cl2" and s["quantum_yield"] == 1e5
    assert any(e["step"] == "Метод синтеза: фотохимический" for e in d["explanation"])


@pytest.mark.parametrize("method, note", [
    ({"type": "photochemical", "wavelength_nm": 650}, "Cl2 - только до 493 нм"),
    ({"type": "photochemical", "wavelength_nm": 450, "intensity_W": 0}, "свет выключен"),
])
def test_no_initiation(agent, method, note):
    d = _run(agent, H2_CL2, method)
    assert d["status"] == "no_reaction" and not d["synthesis"]["initiated"]
    assert any(note in w for w in d["warnings"])


def test_bromine_absorbs_longer_wavelength(agent):
    d = _run(agent, [{"formula": "H2", "moles": 0.1, "phase": "g"}, {"formula": "Br2", "moles": 0.1, "phase": "g"}],
             {"type": "photochemical", "wavelength_nm": 550})
    assert d["synthesis"]["initiated"] and d["summary"]["main_product"] == "HBr"


def test_photon_energy_and_flux():
    assert ph.photon_energy_kJ(450) == pytest.approx(265.8, abs=0.1)
    assert ph.photon_flux_mol_s(1.0, 450) == pytest.approx(3.762e-6, rel=1e-3)
    # порог Cl2 = hc/D0: 119 627 / 242,6 = 493 нм
    assert ph.KJ_NM / 242.6 == pytest.approx(ph.PHOTOLYSIS["Cl2"][0], abs=1)


def test_endergonic_photolysis_warned(agent):
    d = _run(agent, [{"formula": "AgBr", "moles": 0.01, "phase": "s"}], {"type": "photochemical", "wavelength_nm": 400})
    assert d["status"] == "no_reaction" and d["synthesis"]["initiated"]
    assert any("Фотостационарное" in w for w in d["warnings"])


@pytest.mark.parametrize("method, msg", [
    ({"type": "photochemical"}, "wavelength_nm"),
    ("photochemical", "wavelength_nm"),
    ({"type": "laser_magic"}, "method.type"),
    ({"type": "photochemical", "wavelength_nm": 50}, "wavelength_nm"),
])
def test_validation(agent, method, msg):
    d = _run(agent, H2_CL2, method)
    assert d["status"] == "error" and msg in d["message"]
