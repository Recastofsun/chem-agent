"""W-15: пул 100 реакций, структурное сравнение уравнений, электролиз и исправления ядра."""
import json

import pytest

from chem_agent.benchmark import equations_match, parse_equation
from chem_agent.parser.classifier import is_cyanide
from chem_agent.parser.formula import parse_formula
from chem_agent.search.hypotheses import is_organic
from chem_agent.utils.paths import PROJECT_DIR

OPTS = {"include_uncertainty": False, "include_kinetics": False}
POOL = json.loads((PROJECT_DIR / "data" / "pool_100.json").read_text(encoding="utf-8"))


def test_pool_structure():
    assert len(POOL) == 100 and len({r["id"] for r in POOL}) == 100
    cats = {r["category"] for r in POOL}
    assert cats == {"нейтрализация", "осаждение", "ОВР", "комплексы", "разложение", "электрохимия", "газовые"}


def test_equation_comparison():
    assert equations_match("CaCl2 + Na2CO3 -> CaCO3↓ + 2 NaCl", "Na2CO3 + CaCl2 -> 2 NaCl + CaCO3↓")
    assert equations_match("2 H2 + O2 -> 2 H2O", "4 H2 + 2 O2 -> 4 H2O")              # приведение по НОД
    assert not equations_match("CaCO3 -> CaO + CO2↑", "CaCO3 -> CaO + CO2")            # фаза важна
    assert equations_match("CH3COOH + NaOH -> CH3COONa + H2O", "CH3COOH + NaOH -> NaCH3COO + H2O")
    assert parse_equation("2 NaCl -> 2 Na + Cl2↑")[("R", parse_formula("Cl2").key, "g")] == 1


def test_pool_accuracy_and_disputed():
    from scripts.run_pool import run
    rep = run(PROJECT_DIR / "data" / "pool_100.json")
    failed = sorted(r["id"] for r in rep["rows"] if not r["ok"])
    disputed = sorted(r["id"] for r in json.loads((PROJECT_DIR / "data" / "pool_disputed.json").read_text(encoding="utf-8")))
    assert rep["accuracy"] >= 0.96 and failed == disputed


@pytest.mark.parametrize("reagents, voltage, equation", [
    ([("CuCl2", .05)], 2.0, "CuCl2 -> Cu↓ + Cl2↑"),
    ([("NaCl", .1)], 4.0, "2 NaCl + 2 H2O -> 2 NaOH + H2↑ + Cl2↑"),
    ([("CuSO4", .05)], 2.0, "2 CuSO4 + 2 H2O -> 2 Cu↓ + O2↑ + 2 H2SO4"),
    ([("HCl", .1)], 2.0, "2 HCl -> H2↑ + Cl2↑"),
])
def test_electrolysis(agent, reagents, voltage, equation):
    d = agent.predict(reagents=[{"formula": f, "moles": m, "phase": "aq"} for f, m in reagents],
                      conditions={"electrolysis": {"enabled": True, "voltage_V": voltage}}, options=OPTS).data
    assert d["status"] == "ok" and equations_match(equation, d["balanced_equations"][0]["equation"])
    assert d["electrolysis"]["U_decomposition_V"] < voltage


def test_electrolysis_below_decomposition_voltage(agent):
    d = agent.predict(reagents=[{"formula": "NaCl", "moles": .1, "phase": "aq"}],
                      conditions={"electrolysis": {"enabled": True, "voltage_V": 1.0}}, options=OPTS).data
    assert d["status"] == "no_reaction" and d["electrolysis"]["U_decomposition_V"] > 1.0


def test_electrolysis_faraday(agent):
    # 1 А · 965 с = 0,01 моль e-: 0,005 моль Cu
    d = agent.predict(reagents=[{"formula": "CuSO4", "moles": .05, "phase": "aq"}],
                      conditions={"electrolysis": {"enabled": True, "voltage_V": 2.0, "current_A": 1.0,
                                                   "duration_s": 964.85}}, options=OPTS).data
    cu = next(p for p in d["products"] if p["formula"] == "Cu")
    assert cu["moles"] == pytest.approx(0.005, rel=1e-3)


def test_core_fixes(agent):
    # ферроцианид из Fe2+ и CN-: цианид не "распадается", Fe(CN)6-4 разбирается по степеням окисления
    d = agent.predict(reagents=[{"formula": "FeSO4", "moles": .01, "phase": "aq"},
                                {"formula": "KCN", "moles": .06, "phase": "aq"}], options=OPTS).data
    assert d["summary"]["main_product"] == "K4Fe(CN)6"
    # перхлорат из хлорной кислоты - не "новый" перхлорат
    d = agent.predict(reagents=[{"formula": "HClO4", "moles": .1, "phase": "aq"},
                                {"formula": "LiOH", "moles": .1, "phase": "aq"}], options=OPTS).data
    assert d["summary"]["main_product"] == "LiClO4"
    assert is_organic({"C": 2, "H": 3, "N": 1}) and not is_organic({"C": 2, "H": 4})
    assert is_cyanide(parse_formula("KCN")) and not is_cyanide(parse_formula("KSCN"))
