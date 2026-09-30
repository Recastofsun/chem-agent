"""DFT fallback (PySCF) - optional.

Status: not used in v1.0. A gas-phase DFT energy of an isolated molecule is not a
standard Gibbs energy of formation of a solid or of a hydrated ion; turning one into the
other requires thermochemical cycles and solvation models whose error (10-50 kJ/mol) exceeds
the effects being predicted. The source is reported as unavailable instead of guessing.
"""
from __future__ import annotations

import importlib.util


def status() -> dict:
    return {"available": False, "pyscf": importlib.util.find_spec("pyscf") is not None,
            "reason": "DFT-оценка dGf для растворов и твердых фаз ненадежна без термохимических циклов; не используется"}


def energy(formula: str, phase: str):
    return None
