"""W-02: staged balancer - уравнение через промежуточные частицы, когда balance() вернул None."""
import pytest

from chem_agent.parser.formula import parse_formula
from chem_agent.search.balance import balance
from chem_agent.search.staged_balancer import decompose, staged_balance

OPTS = {"include_uncertainty": False, "include_kinetics": False}


def _sides(reac, prod):
    rc = [dict(parse_formula(f).elements) for f in reac]
    rq = [parse_formula(f).charge for f in reac]
    pc = [dict(parse_formula(f).elements) for f in prod]
    pq = [parse_formula(f).charge for f in prod]
    return rc, rq, pc, pq


def _staged(reac, prod, amounts=None, **kw):
    return staged_balance(*_sides(reac, prod), amounts, reac_names=reac, prod_names=prod, **kw)


def test_water_spectator_gets_zero():
    # balance() требует строго положительных коэффициентов и сдается на лишней H2O
    reac, prod = ["Fe", "CuSO4", "H2O"], ["Cu", "FeSO4"]
    assert balance(*_sides(reac, prod)) is None
    r = _staged(reac, prod, [0.01, 0.00999], reac_dissolved=[False, True, False], prod_dissolved=[False, True])
    assert (r.reactants, r.products) == ([1, 1, 0], [1, 1])
    assert [s["stage"] for s in r.stages] == ["dissociation", "ionic", "association"]
    assert r.stages[1]["equation"] == "Cu+2 + Fe -> Cu + Fe+2"


def test_minor_product_dropped():
    r = _staged(["Cl2", "KBr", "H2O"], ["KCl", "Br2", "H+"], [0.0194, 0.0097, 0.00058],
                reac_dissolved=[False, True, False], prod_dissolved=[True, False, True])
    assert (r.reactants, r.products) == ([1, 2, 0], [2, 1, 0])
    assert r.dropped_products == [2]


def test_medium_not_forced_into_equation():
    # H+ и OH- выше 10 % главного продукта, но это среда: в уравнение не тянем
    r = _staged(["Fe+3", "I-", "H2O"], ["Fe+2", "I2", "H+", "OH-"], [0.01, 0.005, 0.002, 0.002], main=0)
    assert (r.reactants, r.products) == ([2, 2, 0], [2, 1, 0, 0])


def test_complexation_stage():
    r = _staged(["NiSO4", "NH3"], ["Ni(NH3)6SO4"], [0.01])
    assert (r.reactants, r.products) == ([1, 6], [1])
    kinds = {s["stage"]: s["equation"] for s in r.stages}
    assert kinds["complexation"] == "6 NH3 + Ni+2 -> Ni(NH3)6+2"


def test_hydroxo_and_complex_decomposition():
    z = decompose(parse_formula("Zn(OH)4-2").key, deep=True)
    assert z == {parse_formula("Zn+2").key: 1.0, parse_formula("OH-").key: 4.0}
    cu = decompose(parse_formula("Cu(NH3)4+2").key, deep=True)
    assert cu == {parse_formula("Cu+2").key: 1.0, parse_formula("NH3").key: 4.0}
    # мелкая декомпозиция: соль на ионы, комплексный ион целый
    k4 = decompose(parse_formula("K4[Fe(CN)6]").key)
    assert k4[parse_formula("Fe(CN)6-4").key] == 1.0 and k4[parse_formula("K+").key] == 4.0


def test_impossible_returns_none():
    assert _staged(["NaCl"], ["KBr"]) is None


def test_agent_uses_staged_for_molecular_equation(agent):
    # Fe + CuSO4 с W-16 (sulfate_only_inert) уравнивается напрямую; Cl2 + KBr - только через стадии
    d = agent.predict(reagents=[{"formula": "Cl2", "moles": 0.005, "phase": "g"},
                                {"formula": "KBr", "moles": 0.01, "phase": "aq"}], options=OPTS).data
    eq = d["balanced_equations"][0]
    assert eq["equation"] == "Cl2 + 2 KBr -> Br2 + 2 KCl"
    assert eq["balancer"] == "staged" and eq["delta_G_kJ_mol"] < 0
    d = agent.predict(reagents=[{"formula": "Fe", "moles": 0.01, "phase": "s"},
                                {"formula": "CuSO4", "moles": 0.01, "phase": "aq"}], options=OPTS).data
    assert d["balanced_equations"][0]["equation"] == "Fe + CuSO4 -> Cu↓ + FeSO4"


@pytest.mark.parametrize("reagents, ionic", [
    ([("Na3PO4", "aq", 0.02), ("CaCl2", "aq", 0.03)], "3 Ca+2 + 2 PO4-3 -> Ca3(PO4)2↓"),
    ([("NiSO4", "aq", 0.01), ("NH3", "aq", 0.1)], "6 NH3 + Ni+2 -> Ni(NH3)6+2"),
])
def test_agent_ionic_equation_balanced(agent, reagents, ionic):
    d = agent.predict(reagents=[{"formula": f, "phase": ph, "moles": m} for f, ph, m in reagents], options=OPTS).data
    assert d["ionic_equation"]["balanced"] and d["ionic_equation"]["equation"] == ionic
