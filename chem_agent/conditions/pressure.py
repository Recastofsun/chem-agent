"""Pressure units. Gas standard state: 1 bar (CRC tables)."""
from __future__ import annotations

ATM_TO_BAR = 1.01325


def atm_to_bar(p_atm: float) -> float:
    return p_atm * ATM_TO_BAR
