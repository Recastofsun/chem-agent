"""Расчет термодинамических величин и lookup в CRC."""
import math
import sqlite3
from pathlib import Path
from typing import Optional

# Константы
T0 = 298.15  # Стандартная температура, K
R = 8.314462618e-3  # Универсальная газовая постоянная, кДж/(моль·К)
RT_LN10 = R * T0 * math.log(10)  # RT·ln(10) ≈ 5.708 кДж/моль


def log_k_to_dg(log_k: float, temperature: float = T0) -> float:
    """Переводит log10(K) в ΔG° (кДж/моль)."""
    return -R * temperature * math.log(10) * log_k


def dg_from_reaction(
    log_k: float,
    reactants_dg: float,
    temperature: float = T0,
) -> float:
    """
    Рассчитывает dGf продукта из dGf реагентов и log_k реакции.
    
    Для реакции: aA + bB = cC
    dGf_C = (a·dGf_A + b·dGf_B) + RT·ln(10)·log_k  (для c=1)
    """
    return reactants_dg + R * temperature * math.log(10) * log_k


def calculate_mineral_dg(
    log_k: float,
    dg_reactants: float,
    dg_products: float,
    temperature: float = T0,
) -> float:
    """
    Рассчитывает dGf минерала из реакции растворения.
    
    Для реакции: Mineral = aA + bB
    dGf_Mineral = (a·dGf_A + b·dGf_B) + RT·ln(10)·log_k
    """
    return dg_products - dg_reactants + R * temperature * math.log(10) * log_k


def get_g_crc(cur: sqlite3.Cursor, formula: str) -> Optional[float]:
    """Ищет dGf в базе данных по формуле (пробует все фазы)."""
    for phase in ('aq', 'l', 'g', 's'):
        row = cur.execute(
            "SELECT dGf FROM species WHERE formula = ? AND phase = ?",
            (formula, phase)
        ).fetchone()
        if row and row[0] is not None:
            return row[0]
    return None


def get_g_from_cache_or_crc(
    cur: sqlite3.Cursor,
    formula: str,
    cache: dict[str, float]
) -> Optional[float]:
    """Ищет dGf сначала в кэше, потом в CRC."""
    if formula in cache:
        return cache[formula]
    g = get_g_crc(cur, formula)
    if g is not None:
        cache[formula] = g
    return g