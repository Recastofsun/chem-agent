"""W-13: разделение равновесного состава - фильтрация, центрифугирование, дистилляция."""
import pytest

from chem_agent.energy.database import get_db
from chem_agent.separation import boiling_point_K

OPTS = {"include_uncertainty": False, "include_kinetics": False}
BASO4 = [{"formula": "BaCl2", "moles": 0.02, "phase": "aq"}, {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}]


def _sep(d, method):
    s = next(x for x in d["separation"] if x["method"] == method)
    return {f["fraction"]: {c["formula"]: c["moles"] for c in f["components"]} for f in s["fractions"]}, s["notes"]


def test_filtration_precipitate(agent):
    d = agent.predict(reagents=BASO4, options={**OPTS, "separation": ["filtration"]}).data
    fr, _ = _sep(d, "filtration")
    assert fr["осадок"] == {"BaSO4": pytest.approx(0.02, rel=5e-3)}  # остаток растворим: ~2e-5 моль
    assert fr["фильтрат"]["Na+"] == pytest.approx(0.04, rel=1e-6) and "BaSO4" not in fr["фильтрат"]


def test_centrifugation_gelatinous(agent):
    d = agent.predict(reagents=[{"formula": "FeCl3", "moles": 0.01, "phase": "aq"},
                                {"formula": "NaOH", "moles": 0.03, "phase": "aq"}],
                      options={**OPTS, "separation": "filtration,centrifugation"}).data
    _, notes_f = _sep(d, "filtration")
    fr, notes_c = _sep(d, "centrifugation")
    assert "Fe(OH)3" in fr["осадок (на дне)"]
    assert any("фильтруется медленно" in n for n in notes_f) and any("центрифугированием" in n for n in notes_c)


def test_distillation_ethanol(agent):
    d = agent.predict(reagents=[{"formula": "Si(OC2H5)4", "moles": 0.01, "phase": "l"}],
                      conditions={"solvent": "water", "method": {"type": "sol_gel", "pH": 2}},
                      options={**OPTS, "separation": ["distillation"]}).data
    s = next(x for x in d["separation"] if x["method"] == "distillation")
    names = [f["fraction"] for f in s["fractions"]]
    assert names[0].startswith("дистиллят") and s["fractions"][0]["components"][0]["formula"] == "C2H5OH"
    assert names[1].startswith("растворитель") and any("Азеотропы" in n for n in s["notes"])


@pytest.mark.parametrize("formula, tb", [("H2O", 373.15), ("C2H5OH", 351.4), ("Br2", 332.0)])
def test_boiling_point_estimate(formula, tb):
    assert boiling_point_K(get_db(), formula) == pytest.approx(tb, abs=6)


def test_invalid_method(agent):
    d = agent.predict(reagents=BASO4, options={**OPTS, "separation": ["sieving"]}).data
    assert d["status"] == "error" and "separation" in d["message"]
