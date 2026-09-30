import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CHEM_AGENT_OFFLINE", "1")
os.environ.setdefault("CHEM_AGENT_DETERMINISTIC", "1")

from chem_agent.utils import offline_guard  # noqa: E402

offline_guard.enable()


@pytest.fixture(scope="session")
def agent():
    from chem_agent.agent import Agent
    return Agent()


def run(agent, reagents, options=None, **cond):
    opts = options or {"include_uncertainty": False, "include_kinetics": False}
    return agent.predict(reagents=reagents, conditions=cond, options=opts).data


def top_keys(products, k=3):
    from chem_agent.parser.formula import parse_formula
    return {parse_formula(p["formula"]).key for p in products[:k]}
