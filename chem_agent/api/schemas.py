"""Request schema for the REST API (full validation is done by parser.validator)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Reagent(BaseModel):
    formula: str
    moles: float | None = None
    mass_g: float | None = None
    phase: str | None = None
    concentration_M: float | None = None
    activity_coefficient: float | None = None
    known_energy: dict[str, Any] | None = None


class PredictRequest(BaseModel):
    reagents: list[Reagent]
    conditions: dict[str, Any] = Field(default_factory=dict)
    known_energies: dict[str, dict[str, Any]] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
