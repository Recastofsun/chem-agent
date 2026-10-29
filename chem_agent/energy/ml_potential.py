"""ML interatomic potentials (MACE / NequIP / Allegro) - optional, local inference only.

Status: NOT USED for predictions in v1.0, by design:
  * MACE-MP-0 and similar universal potentials are trained on periodic crystals
    (Materials Project). They need a 3D structure, not a formula, and they do not give
    Gibbs energies of aqueous ions, pH or activity effects.
  * A formula-only request therefore cannot be answered by them honestly.
The module only reports availability so the report can state why the source was skipped.
"""
from __future__ import annotations

import importlib.util

from ..utils.paths import CACHE_DIR, MODELS_DIR

MODEL_FILES = ("mace_mp_0.model", "mace-mp-0.model")


def status() -> dict:
    torch_ok = importlib.util.find_spec("torch") is not None
    mace_ok = importlib.util.find_spec("mace") is not None
    model = next((p for d in (MODELS_DIR, CACHE_DIR) for n in MODEL_FILES if (p := d / n).exists()), None)
    reason = ("ML-потенциалы требуют кристаллической структуры и не дают dGf ионов в растворе; "
              "в версии 1.0 не используются")
    return {"available": False, "torch": torch_ok, "mace": mace_ok,
            "model_file": str(model) if model else None, "reason": reason}


def energy(formula: str, phase: str):
    """Always None in v1.0 (see module docstring)."""
    return None
