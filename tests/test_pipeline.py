"""W-04: Pipeline - 5 этапов, compact/detailed, ранний выход, тупик, fallback."""
import json

import pytest

from chem_agent.agent import Agent
from chem_agent.pipeline import orchestrator
from chem_agent.thermo.equilibrium import EquilibriumError

OPTS = {"include_uncertainty": False, "include_kinetics": False}
BACL2 = [{"formula": "BaCl2", "moles": 0.02, "phase": "aq"}, {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}]


def _run(agent, reagents, mode, conditions=None):
    return agent.predict(reagents=reagents, conditions=conditions or {},
                         options={**OPTS, "pipeline_mode": mode}).data


def _stages(d):
    return {s["stage"]: s for s in d["pipeline"]["stages"]}


def test_default_mode_is_compact(agent):
    d = agent.predict(reagents=BACL2, options=OPTS).data
    assert d["options"]["pipeline_mode"] == "compact"
    assert d["pipeline"]["stages"] == []
    assert not any(e["step"].startswith("Pipeline") for e in d["explanation"])


def test_invalid_mode_rejected(agent):
    d = agent.predict(reagents=BACL2, options={**OPTS, "pipeline_mode": "verbose"}).data
    assert d["status"] == "error" and "pipeline_mode" in d["message"]


def test_detailed_reports_five_stages_and_same_result(agent):
    c, d = _run(agent, BACL2, "compact"), _run(agent, BACL2, "detailed")
    assert json.dumps(c["final_composition"], sort_keys=True) == json.dumps(d["final_composition"], sort_keys=True)
    st = _stages(d)
    assert d["pipeline"]["order"] == [1, 2, 3, 4, 5] and sorted(st) == [1, 2, 3, 4, 5]
    assert {x["formula"] for x in st[1]["formed"]} == {"Ba+2", "Cl-", "Na+", "SO4-2"}
    assert st[3]["status"] == "done" and [f for f, _ in st[3]["supersaturated"]] == ["BaSO4"]
    assert st[3]["formed"][0]["formula"] == "BaSO4"
    steps = [e["step"] for e in d["explanation"] if e["step"].startswith("Pipeline")]
    assert len(steps) == 5 and steps[2] == "Pipeline, этап 3: Осаждение"


def test_si_not_reported_for_species_outside_span(agent):
    # металлический Ba при исключенных редокс-частицах давал ложный SI 17,7
    st = _stages(_run(agent, BACL2, "detailed"))
    assert "Ba" not in {f for f, _ in st[3]["supersaturated"]}


def test_complexation_stage(agent):
    d = _run(agent, [{"formula": "NiSO4", "moles": 0.01, "phase": "aq"},
                     {"formula": "NH3", "moles": 0.1, "phase": "aq"}], "detailed")
    assert _stages(d)[2]["formed"][0]["formula"] == "Ni(NH3)6+2"


def test_equation_stages_in_detailed(agent):
    # уравнение от staged balancer (W-02): стадии видны в detailed, в compact - нет
    r = [{"formula": "Cl2", "moles": 0.005, "phase": "g"}, {"formula": "KBr", "moles": 0.01, "phase": "aq"}]
    steps = {e["step"]: e["text"] for e in _run(agent, r, "detailed")["explanation"]}
    assert steps["Стадия уравнения (ионная стадия)"] == "2 Br- + Cl2 -> Br2 + 2 Cl-"
    assert not any(e["step"].startswith("Стадия") for e in _run(agent, r, "compact")["explanation"])


def test_early_exit(agent):
    d = _run(agent, [{"formula": "HCl", "moles": 0.01, "phase": "aq"},
                     {"formula": "NaOH", "moles": 0.01, "phase": "aq"}], "detailed")
    st = _stages(d)
    assert d["pipeline"]["early_exit"] is True
    assert all(st[k]["status"] == "skipped" and "ранний выход" in st[k]["reason"] for k in (2, 3, 4))
    assert st[5]["status"] == "done" and d["summary"]["main_product"] == "NaCl"


def test_dry_system_gas_stage(agent):
    d = _run(agent, [{"formula": "CaCO3", "moles": 0.01, "phase": "s"}], "detailed",
             {"temperature_K": 1200, "solvent": "none"})
    st = _stages(d)
    assert st[1]["status"] == st[2]["status"] == "skipped"
    assert {x["formula"] for x in st[4]["formed"]} >= {"CaO", "CO2"}


class _StubbornCond:
    """Обертка над решателем: равновесие с твердыми фазами без газов не сходится."""

    def __init__(self, solver):
        self._s = solver

    def __getattr__(self, k):
        return getattr(self._s, k)

    def run(self, dG_shift=None, b=None, warm=None):
        eq = self._s.run(dG_shift=dG_shift, b=b, warm=warm)
        if dG_shift is not None:
            kinds = self._s.system.kinds
            cond_on = any(k == "cond" and d == 0 for k, d in zip(kinds, dG_shift))
            gas_on = any(k == "g" and d == 0 for k, d in zip(kinds, dG_shift))
            if cond_on and not gas_on and any(k == "g" for k in kinds):
                eq.converged = False
        return eq


def test_dead_end_on_precipitation_switches_order(agent, monkeypatch):
    real = orchestrator.run_stages
    monkeypatch.setattr(orchestrator, "run_stages", lambda solver, order=orchestrator.DEFAULT_ORDER:
                        real(_StubbornCond(solver), order))
    d = _run(agent, [{"formula": "CaCO3", "moles": 0.01, "phase": "s"}], "detailed",
             {"temperature_K": 1200, "solvent": "none"})
    assert d["pipeline"]["order"] == [1, 2, 4, 3, 5]
    assert "Pipeline: тупик" in [e["step"] for e in d["explanation"]]
    assert d["summary"]["main_product"] == "CaO"


def test_warm_restart_when_full_solve_fails(agent, monkeypatch):
    real = Agent._equilibrium

    def flaky(self, solver, titration, warm=None):
        if warm is None:
            raise EquilibriumError("не сошлось с нуля")
        return real(self, solver, titration, warm)
    monkeypatch.setattr(Agent, "_equilibrium", flaky)
    d = _run(agent, BACL2, "compact")
    assert d["status"] == "ok" and d["summary"]["main_product"] == "BaSO4"
    assert d["pipeline"]["fallback"] == "warm_restart" and len(d["pipeline"]["stages"]) == 5
    assert any("повторен от состава этапов Pipeline" in w for w in d["warnings"])


def test_unknown_when_nothing_converges(agent, monkeypatch):
    def broken(self, solver, titration, warm=None):
        raise EquilibriumError("нет решения")
    monkeypatch.setattr(Agent, "_equilibrium", broken)
    d = _run(agent, BACL2, "compact")
    assert d["status"] == "unknown" and d["pipeline"]["fallback"] == "unknown"
    assert d["message"].startswith("неизвестно")
