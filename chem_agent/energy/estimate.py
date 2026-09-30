"""Empirical estimates.

Policy: no "smart guesses". The only estimate allowed is the one fully determined by
tabulated data: dGf(T) extrapolation with constant dHf and dSf (see thermo.gibbs).
Species without tabulated dGf are reported as "неизвестно".
"""
from __future__ import annotations


def status() -> dict:
    return {"available": True,
            "reason": "только экстраполяция dGf(T) при постоянных dHf и dSf; новых значений не придумывает"}


def energy(formula: str, phase: str):
    return None
