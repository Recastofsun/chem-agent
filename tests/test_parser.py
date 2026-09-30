import pytest

from chem_agent.parser.formula import FormulaError, parse_formula
from chem_agent.parser.naming import display_formula, russian_name
from chem_agent.parser.oxidation import oxidation_states
from chem_agent.parser.validator import ValidationError, validate
from chem_agent.search.balance import balance


@pytest.mark.parametrize("f,els,q", [
    ("H2SO4", {"H": 2, "S": 1, "O": 4}, 0), ("Ca3(PO4)2", {"Ca": 3, "P": 2, "O": 8}, 0),
    ("K4[Fe(CN)6]", {"K": 4, "Fe": 1, "C": 6, "N": 6}, 0), ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}, 0),
    ("CuSO4*5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}, 0), ("SO4-2", {"S": 1, "O": 4}, -2),
    ("SO4^2-", {"S": 1, "O": 4}, -2), ("Fe3+", {"Fe": 1}, 3), ("Fe+3", {"Fe": 1}, 3), ("NH4+", {"N": 1, "H": 4}, 1),
    ("Al(OH)4-", {"Al": 1, "O": 4, "H": 4}, -1), ("H₂O", {"H": 2, "O": 1}, 0), ("Fe⁺³", {"Fe": 1}, 3),
])
def test_parse(f, els, q):
    c = parse_formula(f)
    assert c.as_dict == els and c.charge == q


def test_phase_suffix():
    assert parse_formula("NaCl(aq)").phase == "aq"
    assert parse_formula("CO2(г)").phase == "g"
    assert parse_formula("Cu(OH)2(тв)").phase == "s"


@pytest.mark.parametrize("bad", ["", "Xx2", "Cu(OH", "H2O)", "2H"])
def test_bad_formula(bad):
    with pytest.raises(FormulaError):
        parse_formula(bad)


def test_molar_mass():
    assert abs(parse_formula("H2O").molar_mass() - 18.015) < 0.01
    assert abs(parse_formula("Na2SO4").molar_mass() - 142.04) < 0.05


@pytest.mark.parametrize("f,disp", [("Cu(OH)2", "Cu(OH)2"), ("BaSO4", "BaSO4"), ("Ca3(PO4)2", "Ca3(PO4)2"),
                                     ("(NH4)2SO4", "(NH4)2SO4"), ("NaCl", "NaCl"), ("Fe2(SO4)3", "Fe2(SO4)3")])
def test_display(f, disp):
    assert display_formula(parse_formula(f)) == disp


def test_russian_names():
    assert russian_name(parse_formula("BaSO4")) == "сульфат бария"
    assert russian_name(parse_formula("H2O")) == "вода"


@pytest.mark.parametrize("f,el,st", [("KMnO4", "Mn", 7), ("K2Cr2O7", "Cr", 6), ("H2O2", "O", -1), ("NaH", "H", -1),
                                     ("CuSO4", "S", 6), ("FeCl3", "Fe", 3), ("NO2", "N", 4), ("NOBr", "N", 3)])
def test_oxidation(f, el, st):
    c = parse_formula(f)
    assert abs(oxidation_states(c.elements, c.charge)[el] - st) < 1e-9


@pytest.mark.parametrize("r,p,cr,cp", [
    (["H2", "O2"], ["H2O"], [2, 1], [2]),
    (["Al", "Fe2O3"], ["Al2O3", "Fe"], [2, 1], [1, 2]),
    (["KMnO4", "HCl"], ["KCl", "MnCl2", "Cl2", "H2O"], [2, 16], [2, 2, 5, 8]),
    (["C3H8", "O2"], ["CO2", "H2O"], [1, 5], [3, 4]),
])
def test_balance(r, p, cr, cp):
    rc = [parse_formula(x) for x in r]
    pc = [parse_formula(x) for x in p]
    res = balance([c.as_dict for c in rc], [0] * len(rc), [c.as_dict for c in pc], [0] * len(pc))
    assert res == (cr, cp)


def test_ionic_balance_with_charge():
    rc = [parse_formula(x) for x in ["MnO4-", "Fe+2", "H+"]]
    pc = [parse_formula(x) for x in ["Mn+2", "Fe+3", "H2O"]]
    res = balance([c.as_dict for c in rc], [c.charge for c in rc], [c.as_dict for c in pc], [c.charge for c in pc])
    assert res == ([1, 5, 8], [1, 5, 4])


def test_validator_defaults():
    req, _ = validate({"reagents": [{"formula": "NaOH", "moles": 1}]})
    assert req["conditions"]["temperature_K"] == 298.15
    assert req["conditions"]["solvent"]["name"] == "water"
    assert req["options"]["accuracy"] == "balanced"


@pytest.mark.parametrize("bad", [
    {"reagents": []}, {"reagents": [{"formula": "NaOH", "moles": -1}]},
    {"reagents": [{"formula": "NaOH", "moles": 1}], "conditions": {"temperature_K": 10}},
    {"reagents": [{"formula": "NaOH", "moles": 1}], "conditions": {"solvent": "ethanol"}},
    {"reagents": [{"formula": "NaOH", "moles": 1}], "options": {"accuracy": "super"}},
    {"reagents": [{"formula": "Qq", "moles": 1}]},
])
def test_validator_errors(bad):
    with pytest.raises(ValidationError):
        validate(bad)


def test_mass_input():
    req, _ = validate({"reagents": [{"formula": "NaCl", "mass_g": 58.44}]})
    assert abs(req["reagents"][0]["moles"] - 1.0) < 1e-3
