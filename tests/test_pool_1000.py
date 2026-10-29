"""W-16: пул 1000 реакций и исправления ядра и данных, найденные им."""
import json

import pytest

from chem_agent.utils.paths import PROJECT_DIR

OPTS = {"include_uncertainty": False, "include_kinetics": False}


def _p(agent, reagents, **cond):
    return agent.predict(reagents=[{"formula": f, "moles": m, "phase": ph} for f, m, ph in reagents],
                         conditions=cond, options=OPTS).data


def test_pool_1000_accuracy_and_disputed():
    from scripts.run_pool import run
    pool = json.loads((PROJECT_DIR / "data" / "pool_1000.json").read_text(encoding="utf-8"))
    assert len(pool) == 1000 and len({r["id"] for r in pool}) == 1000
    rep = run(PROJECT_DIR / "data" / "pool_1000.json")
    failed = sorted(r["id"] for r in rep["rows"] if not r["ok"])
    disputed = json.loads((PROJECT_DIR / "data" / "pool_disputed_1000.json").read_text(encoding="utf-8"))
    assert rep["accuracy"] >= 0.98 and failed == sorted(r["id"] for r in disputed)
    assert all(r["reason"] != "не разобрано" for r in disputed)


def test_titanium_oxide_record(agent):
    # запись 'TiO' была Ti3O5 (ΔfG -2317 кДж/моль): Ti + O2 давал TiO
    d = _p(agent, [("Ti", .01, "s"), ("O2", .01, "g")], solvent="none", temperature_K=900)
    assert d["summary"]["main_product"] == "TiO2"


@pytest.mark.parametrize("salt, metal", [("CuSO4", "Cu"), ("SnCl2", "Sn")])
def test_metal_displacement_fixed(agent, salt, metal):
    # Mn(0) был отрезан правилом mn_neutral_stop; SnCl2(aq) был на 140 кДж стабильнее ионов
    m = "Mn" if salt == "CuSO4" else "Fe"
    d = _p(agent, [(m, .01, "s"), (salt, .01, "aq")], solvent="water")
    assert d["summary"]["main_product"] == metal


def test_sulfate_not_reduced_with_cu2(agent):
    # Cu2+ - "сильный окислитель", sulfate_inert не срабатывал: Sn + CuSO4 давал Cu2S
    d = _p(agent, [("Sn", .01, "s"), ("CuSO4", .01, "aq")], solvent="water")
    assert "Cu2S" not in {p["formula"] for p in d["products"]}


def test_ammine_not_paired_with_ammonium(agent):
    d = _p(agent, [("NiCl2", .002, "aq"), ("NH3", .5, "aq")], solvent="water")
    assert d["summary"]["main_product"] == "Ni(NH3)6Cl2"


def test_cyanide_salt_of_forbidden_ion(agent):
    # NaHCOO(тв) и (NH4)2SO4(тв) обходили запрет HCOO- и NH4+ правила cyanide_no_hydrolysis
    d = _p(agent, [("FeSO4", .005, "aq"), ("NaCN", .03, "aq")], solvent="water")
    forms = {p["formula"] for p in d["products"]}
    assert d["summary"]["main_product"] == "Na4Fe(CN)6" and not forms & {"NaHCOO", "(NH4)2SO4"}


def test_open_dry_system_no_sublimation(agent):
    # при P -> 0 KCl испарялся при 900 K (давление пара 2e-5 бар)
    d = _p(agent, [("KClO3", .02, "s")], solvent="none", temperature_K=900, atmosphere={"mode": "open"})
    kcl = next(p for p in d["products"] if p["formula"] == "KCl")
    assert kcl["phase"] == "s"
    assert any("не испаряются" in w for w in d["warnings"])


def test_mn_hydroxide_decomposes(agent):
    d = _p(agent, [("Mn(OH)2", .01, "s")], solvent="none", temperature_K=600)
    assert d["summary"]["main_product"] == "MnO"
