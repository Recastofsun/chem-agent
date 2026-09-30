"""Hypothesis generation, kinetic rules and ranking."""
from chem_agent.parser.formula import parse_formula
from chem_agent.search.hypotheses import is_organic
from chem_agent.search.rules import Reagent, RuleContext, evaluate
from tests.conftest import run, top_keys


def _ctx(formulas, T=298.15, aqueous=True, V=1.0):
    return RuleContext(T=T, aqueous=aqueous, volume_L=V,
                       reagents=[Reagent(f, parse_formula(f), m, "aq") for f, m in formulas])


def test_is_organic():
    assert is_organic({"C": 1, "H": 4})
    assert is_organic({"C": 2, "H": 4, "O": 2})
    assert not is_organic({"C": 1, "H": 1, "O": 3})   # HCO3-
    assert not is_organic({"C": 1, "O": 2})
    assert not is_organic({"H": 1, "C": 1, "N": 1})   # HCN


def test_rules_sulfate_inert_in_dilute_acid():
    out = evaluate(_ctx([("Zn", 0.02), ("H2SO4", 0.02)]))
    assert out.decouple["S"] == [[6], ["others"]]


def test_rules_conc_hot_sulfuric():
    out = evaluate(_ctx([("Cu", 0.1), ("H2SO4", 1.0)], T=400, V=0.05))
    assert out.decouple["S"] == [[6, 4], ["others"]]


def test_rules_no_h2_from_neutral_water():
    out = evaluate(_ctx([("Fe", 0.02), ("CuSO4", 0.02)]))
    assert parse_formula("H2").key in out.forbid_new


def test_rules_h2_allowed_with_acid():
    out = evaluate(_ctx([("Zn", 0.02), ("HCl", 0.05)]))
    assert parse_formula("H2").key not in out.forbid_new


def test_rule_can_be_disabled():
    out = evaluate(_ctx([("Fe", 0.02), ("CuSO4", 0.02)]), disabled={"water_not_reduced"})
    assert parse_formula("H2").key not in out.forbid_new


def test_precipitation_hypothesis(agent):
    r = run(agent, [{"formula": "AgNO3", "moles": 0.02, "phase": "aq"}, {"formula": "NaCl", "moles": 0.02, "phase": "aq"}])
    assert r["products"][0]["formula"] == "AgCl" and r["products"][0]["kind"] == "precipitate"
    assert parse_formula("NaNO3").key in top_keys(r["products"])


def test_displacement(agent):
    r = run(agent, [{"formula": "Fe", "moles": 0.02, "phase": "s"}, {"formula": "CuSO4", "moles": 0.02, "phase": "aq"}])
    assert r["products"][0]["formula"] == "Cu"
    assert parse_formula("FeSO4").key in top_keys(r["products"])


def test_no_displacement(agent):
    r = run(agent, [{"formula": "Cu", "moles": 0.02, "phase": "s"}, {"formula": "FeSO4", "moles": 0.02, "phase": "aq"}])
    assert r["status"] == "no_reaction"


def test_hydroxide_not_oxide(agent):
    r = run(agent, [{"formula": "CuSO4", "moles": 0.02, "phase": "aq"}, {"formula": "NaOH", "moles": 0.04, "phase": "aq"}])
    assert r["products"][0]["formula"] == "Cu(OH)2"


def test_permanganate_oxidizes_ferrous(agent):
    r = run(agent, [{"formula": "KMnO4", "moles": 0.004, "phase": "aq"}, {"formula": "FeSO4", "moles": 0.02, "phase": "aq"},
                    {"formula": "H2SO4", "moles": 0.02, "phase": "aq"}])
    keys = top_keys(r["products"], 5)
    assert parse_formula("MnSO4").key in keys
    assert parse_formula("Fe2(SO4)3").key in keys


def test_forbidden_products_respected(agent):
    r = agent.predict(reagents=[{"formula": "Zn", "moles": 0.02, "phase": "s"}, {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
                      constraints={"forbidden_products": ["H2"]},
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    assert all(p["formula"] != "H2" for p in r["products"])


def test_explanation_lists_fired_rules(agent):
    r = run(agent, [{"formula": "Zn", "moles": 0.02, "phase": "s"}, {"formula": "H2SO4", "moles": 0.02, "phase": "aq"}])
    ids = {f["id"] for f in r["rules_fired"]}
    assert "sulfate_inert" in ids
    assert any("Правило" in e["step"] for e in r["explanation"])


def test_ranking_prefers_precipitate(agent):
    r = run(agent, [{"formula": "BaCl2", "moles": 0.02, "phase": "aq"}, {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}])
    kinds = [p["kind"] for p in r["products"]]
    assert kinds[0] == "precipitate"
    scores = [p["score"] for p in r["products"]]
    assert scores == sorted(scores, reverse=True)
