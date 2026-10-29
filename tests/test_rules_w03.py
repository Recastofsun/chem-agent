"""W-03: rules.yaml сокращен до фундаментальных правил, остальное - kinetic_barriers (Ea) и classifier."""
import pytest

from chem_agent.energy.database import get_db
from chem_agent.parser.classifier import is_inert, is_perchlorate
from chem_agent.parser.formula import parse_formula
from chem_agent.search.rules import (Reagent, RuleContext, eyring_half_life, evaluate, kinetically_blocked,
                                     load_kinetic_rules, load_rules)

TZ_RULES = {"n2_inert", "water_not_reduced", "gas_mix_no_igniter", "hydroxides_not_oxides", "no_perchlorate"}


def _ctx(formulas, T=298.15, aqueous=True, phase="aq", **kw):
    return RuleContext(T=T, aqueous=aqueous, volume_L=1.0,
                       reagents=[Reagent(f, parse_formula(f), m, phase) for f, m in formulas], **kw)


def test_rules_yaml_is_5_to_7_fundamental():
    ids = [r["id"] for r in load_rules()]
    assert 5 <= len(ids) <= 7 and TZ_RULES <= set(ids)


def test_kinetic_rules_from_db():
    rules = load_kinetic_rules()
    assert len(rules) == 33  # 29 из v2.4 + organic_skeleton_lowT (W-04), aluminosilicate_lowT (W-07), cyanide_no_hydrolysis (W-15), sulfate_only_inert (W-16)
    ids = {r["id"] for r in rules}
    assert not ids & {r["id"] for r in load_rules()}
    assert len(ids) == len(rules)  # дубль carbide_hydrolysis_acetylene объединен


def test_ea_reproduces_temperature_threshold():
    # nitrogen_redox_lowT в v2.4: T_below 450. Ea подобрана так, что t1/2 = 1 ч при 450 K
    ea = next(r["ea_kj_mol"] for r in load_kinetic_rules() if r["id"] == "nitrogen_redox_lowT")
    assert ea == pytest.approx(143.76, abs=0.01)
    assert eyring_half_life(ea, 450.0) == pytest.approx(3600, rel=0.01)
    assert kinetically_blocked(ea, 449.0) and not kinetically_blocked(ea, 450.0)
    assert kinetically_blocked(None, 5000.0)  # без Ea - правило селективности, всегда в силе


def test_nitrate_rule_switches_off_above_threshold():
    low = evaluate(_ctx([("Cu", 0.01), ("HNO3", 0.1)], T=400.0))
    high = evaluate(_ctx([("Cu", 0.01), ("HNO3", 0.1)], T=500.0))
    assert "nitrogen_redox_lowT" in {f["id"] for f in low.fired}
    assert "nitrogen_redox_lowT" not in {f["id"] for f in high.fired}
    assert next(f for f in low.fired if f["id"] == "nitrogen_redox_lowT")["ea_kj_mol"] == pytest.approx(143.76)


def test_disabled_rules_apply_to_db_rules():
    out = evaluate(_ctx([("Cu", 0.01), ("HNO3", 0.1)]), disabled={"nitrogen_redox_lowT"})
    assert "nitrogen_redox_lowT" not in {f["id"] for f in out.fired}


@pytest.mark.parametrize("formulas, catalyst, expected", [
    ([("H2", 0.1), ("O2", 0.05)], False, True),
    ([("H2", 0.1), ("O2", 0.05)], True, False),
    ([("NH3", 0.1), ("HCl", 0.1)], False, False),
])
def test_gas_mix_no_igniter(formulas, catalyst, expected):
    out = evaluate(_ctx(formulas, aqueous=False, phase="g", catalyst=catalyst))
    assert out.no_reaction is expected


def test_gas_mix_through_agent(agent):
    d = agent.predict(reagents=[{"formula": "H2", "moles": 0.1, "phase": "g"},
                                {"formula": "O2", "moles": 0.05, "phase": "g"}],
                      conditions={"solvent": "none"},
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    assert d["summary"]["reaction_occurred"] is False
    assert "gas_mix_no_igniter" in {f["id"] for f in d["rules_fired"]}


def test_classifier_perchlorate_and_inert():
    assert all(is_perchlorate(parse_formula(f)) for f in ("ClO4-", "HClO4", "KClO4"))
    assert not any(is_perchlorate(parse_formula(f)) for f in ("ClO3-", "Cl-", "HClO"))
    assert is_inert(parse_formula("N2")) and is_inert(parse_formula("Ar"))
    assert not is_inert(parse_formula("O2"))


def test_complex_constants():
    c = get_db().get_complex("Cu(NH3)4+2")
    assert c["metal"] == "Cu+2" and c["ligand"] == "NH3" and c["n"] == 4 and c["log_beta"] == pytest.approx(13.0)
    assert get_db().get_complex("FeSCN+2")["log_beta"] == pytest.approx(3.03)


# --- исправление W-04: cyanide_complexes_stable срабатывал в любой водной реакции и запрещал CO2, NH3, CO

@pytest.mark.parametrize("reagents, gas", [
    ([("Na2CO3", 0.01), ("HCl", 0.02)], "CO2"),
    ([("NH4Cl", 0.01), ("NaOH", 0.01)], "NH3"),
])
def test_carbonate_and_ammonium_release_gas(agent, reagents, gas):
    d = agent.predict(reagents=[{"formula": f, "moles": m, "phase": "aq"} for f, m in reagents],
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    assert gas in [p["formula"] for p in d["products"][:3]]
    assert "cyanide_complexes_stable" not in {f["id"] for f in d["rules_fired"]}


def test_cyanide_rule_needs_cyanide_complex():
    from chem_agent.parser.classifier import is_cyanide_complex
    assert all(is_cyanide_complex(parse_formula(f)) for f in ("K3(Fe(CN)6)", "K4[Fe(CN)6]", "Ag(CN)2-"))
    assert not any(is_cyanide_complex(parse_formula(f)) for f in ("KCN", "HCN", "KSCN", "Na2CO3"))
    fired = lambda fs: {f["id"] for f in evaluate(_ctx([(f, 0.01) for f in fs])).fired}
    assert "cyanide_complexes_stable" in fired(["K3(Fe(CN)6)", "KOH"])
    assert "cyanide_complexes_stable" not in fired(["Na2CO3", "HCl"])


@pytest.mark.parametrize("reagents, main, exclude", [
    ([("CH3COOH", 0.1), ("NaOH", 0.1)], "NaCH3COO", {"CH4", "Na2C2O4"}),
    ([("CH3COONa", 0.1), ("HCl", 0.1)], "CH3COOH", {"CO", "HNaC2O4"}),
])
def test_organic_skeleton_stable(agent, reagents, main, exclude):
    # без cyanide-правила стал виден распад ацетата на CH4 + оксалат; organic_skeleton_lowT его запрещает
    d = agent.predict(reagents=[{"formula": f, "moles": m, "phase": "aq"} for f, m in reagents],
                      options={"include_uncertainty": False, "include_kinetics": False}).data
    formulas = [p["formula"] for p in d["products"]]
    assert formulas[0] == main and not exclude & set(formulas)


def test_organic_salt_is_organic_reagent():
    assert RuleContext.is_organic(parse_formula("CH3COONa"))
    assert not RuleContext.is_organic(parse_formula("K4[Fe(CN)6]"))
    assert not RuleContext.is_organic(parse_formula("Na2C2O4"))
