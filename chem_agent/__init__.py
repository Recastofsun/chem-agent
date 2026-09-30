"""chem-agent: local offline predictor of inorganic reaction products (Gibbs minimization)."""
from __future__ import annotations

import os

__version__ = "1.0.0"

if os.environ.get("CHEM_AGENT_OFFLINE") == "1":
    from .utils import offline_guard as _og

    _og.enable()


def __getattr__(name):
    if name in ("Agent", "Result", "predict"):
        from . import agent as _agent
        return getattr(_agent, name)
    raise AttributeError(name)


__all__ = ["Agent", "Result", "predict", "__version__"]
