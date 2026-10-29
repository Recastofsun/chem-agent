"""W-09: золь-гель метод - гидролиз алкоксида, конденсация, pH и выдержка (Si(OC2H5)4 -> SiO2)."""
import pytest

from chem_agent.synthesis import sol_gel as sg

OPTS = {"include_uncertainty": False, "include_kinetics": False}
TEOS = [{"formula": "Si(OC2H5)4", "moles": 0.01, "phase": "l"}]


def _run(agent, method, solvent="water", reagents=TEOS):
    return agent.predict(reagents=reagents, conditions={"solvent": solvent, "method": method}, options=OPTS).data


def test_teos_to_silica(agent):
    # без метода этанол запрещен правилом "новая органика только как сопряженная форма реагента"
    assert _run(agent, None)["status"] == "no_reaction"
    d = _run(agent, {"type": "sol-gel", "pH": 2, "aging_time_h": 24})
    assert d["status"] == "ok" and d["summary"]["main_product"] == "SiO2"
    assert d["balanced_equations"][0]["equation"] == "Si(OC2H5)4 + 2 H2O -> SiO2↓ + 4 C2H5OH"
    assert d["balanced_equations"][0]["delta_G_kJ_mol"] < 0
    s = d["synthesis"]
    assert s["gelled"] and s["alcohols"] == ["C2H5OH"] and s["gel_type"].startswith("полимерный")


def test_short_aging_gives_sol(agent):
    # pH 7: гидролиз медленный, за 1 ч гель не образуется - остается золь Si(OH)4
    d = _run(agent, {"type": "sol_gel", "pH": 7, "aging_time_h": 1})
    assert not d["synthesis"]["gelled"] and d["summary"]["main_product"] == "Si(OH)4"
    assert any("остается золем" in w for w in d["warnings"])


def test_ph_dependence():
    # минимум скорости около pH 7, кислотный и основной катализ
    t2, t7, t11 = (sg.hydrolysis_half_life_s(x) for x in (2, 7, 11))
    assert t7 > 100 * t2 and t7 > 10 * t11
    assert t2 == pytest.approx(100, rel=0.05)


def test_base_catalysis_colloidal(agent):
    d = _run(agent, {"type": "sol_gel", "pH": 11, "aging_time_h": 48})
    assert d["synthesis"]["gel_type"].startswith("коллоидный") and d["summary"]["main_product"] == "SiO2"


def test_teos_thermo():
    # ΔfG = ΔfH - T·ΔfS: -1408,0 + 298,15·1,2487 = -1035,7 кДж/моль (van der Vis, Cordfunke 1993)
    from chem_agent.energy.database import get_db
    s = next(x for x in get_db().species if x.formula == "Si(OC2H5)4")
    assert s.dHf == -1408.0 and s.dGf == pytest.approx(-1035.69, abs=0.01)


def test_needs_water(agent):
    d = _run(agent, {"type": "sol_gel"}, solvent="none")
    assert d["status"] == "error" and "water" in d["message"]
