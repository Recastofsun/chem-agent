"""Reference set (tests/fixtures/reactions.json, 200+ reactions): Accuracy@3 >= 85 %, speed, determinism."""
import json
import time
from pathlib import Path

import pytest

from chem_agent.benchmark import evaluate, load_reference

FIX = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def bench(agent):
    return evaluate(agent, load_reference())


def test_reference_size():
    ref = load_reference()
    assert len(ref) >= 200
    assert len({r["id"] for r in ref}) == len(ref)


def test_accuracy_at_3(bench):
    assert bench["n_in_scope"] >= 180
    assert bench["accuracy_at_k"] >= 0.85, [r for r in bench["rows"] if not r["ok"] and r["in_scope"]]


def test_blind_holdout(agent):
    """60 reactions written by a separate agent that never saw the rules or the reference set."""
    ref = json.loads((FIX / "holdout.json").read_text(encoding="utf-8"))
    res = evaluate(agent, ref)
    assert res["n_in_scope"] == 60
    assert res["accuracy_at_k"] >= 0.85


def test_no_crashes(bench):
    errs = [r for r in bench["rows"] if r["status"] == "error"]
    assert not errs, errs


def test_no_reaction_cases_not_hallucinated(bench):
    rows = [r for r in bench["rows"] if r["category"] == "no_reaction"]
    assert rows and sum(r["ok"] for r in rows) / len(rows) >= 0.9


def test_expected_outputs_snapshot(agent):
    """Frozen outputs for a few inputs (tests/fixtures/expected): guards against silent regressions."""
    for f in sorted((FIX / "inputs").glob("*.json")):
        req = json.loads(f.read_text(encoding="utf-8"))
        exp = json.loads((FIX / "expected" / f.name).read_text(encoding="utf-8"))
        d = agent.predict(request=req).data
        assert d["status"] == exp["status"], f.name
        assert [p["formula"] for p in d["products"][:3]] == exp["top3"], f.name
        if exp.get("delta_G_kJ_mol") is not None:
            assert abs(d["summary"]["delta_G_kJ_mol"] - exp["delta_G_kJ_mol"]) < 0.05, f.name


def test_speed_balanced_and_fast(agent):
    reag = [{"formula": "KMnO4", "moles": 0.004, "phase": "aq"}, {"formula": "FeSO4", "moles": 0.02, "phase": "aq"},
            {"formula": "H2SO4", "moles": 0.02, "phase": "aq"}]
    t = time.perf_counter()
    agent.predict(reagents=reag, options={"accuracy": "balanced"})
    assert time.perf_counter() - t <= 30.0
    t = time.perf_counter()
    agent.predict(reagents=reag, options={"accuracy": "fast"})
    assert time.perf_counter() - t <= 5.0


def test_determinism(agent):
    req = {"reagents": [{"formula": "Zn", "moles": 0.02, "phase": "s"}, {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
           "options": {"accuracy": "fast"}}
    a = agent.predict(request=req)
    b = agent.predict(request=req)
    ja = json.loads(a.to_json())
    jb = json.loads(b.to_json())
    for d in (ja, jb):
        d["metadata"].pop("compute_time_s")
    assert ja == jb
