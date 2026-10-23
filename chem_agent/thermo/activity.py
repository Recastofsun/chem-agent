"""Activity coefficient models for aqueous solutes (molal scale)."""
from __future__ import annotations

import math
from typing import Callable

import numpy as np

LN10 = math.log(10.0)
MODELS = ("ideal", "debye_huckel", "davies", "pitzer", "sit")


def water_density(T: float) -> float:
    """g/cm3, Thiesen-type correlation, valid 0-100 C (clipped outside)."""
    t = min(max(T - 273.15, 0.0), 150.0)
    return 1 - (t + 288.9414) / (508929.2 * (t + 68.12963)) * (t - 3.9863) ** 2


def water_dielectric(T: float) -> float:
    """Malmberg & Maryott (1956), 0-100 C."""
    t = min(max(T - 273.15, 0.0), 150.0)
    return 87.740 - 0.40008 * t + 9.398e-4 * t ** 2 - 1.410e-6 * t ** 3


def dh_constants(T: float, eps: float | None = None, rho: float | None = None) -> tuple[float, float]:
    """Debye-Huckel A (kg^0.5 mol^-0.5, log10) and B (kg^0.5 mol^-0.5 A^-1)."""
    eps = eps or water_dielectric(T)
    rho = rho or water_density(T)
    A = 1.82483e6 * math.sqrt(rho) / (eps * T) ** 1.5
    B = 50.2916 * math.sqrt(rho) / math.sqrt(eps * T)
    return A, B


def make_sit_matrix(species_list, db) -> np.ndarray:
    """Строит матрицу параметров SIT (epsilon) для списка частиц."""
    n = len(species_list)
    matrix = np.zeros((n, n))
    
    # Получаем список имен (формул) ионов
    formulas = [s.formula for s in species_list]
    
    for i, f1 in enumerate(formulas):
        for j, f2 in enumerate(formulas):
            if i == j:
                continue
            # Параметр SIT ищем в базе. Если нет - берем 0.
            # В базе SIT хранится для пар ионов.
            eps = db.get_sit(f1, f2)
            matrix[i, j] = eps
            
    return matrix


def make_gamma_fn(model: str, T: float, eps: float | None = None, ion_size_A: float = 4.0,
                  species_list=None, db=None) -> Callable:
    """
    Возвращает функцию f(I, z, m) -> ln(gamma).
    m - массив моляльностей (нужен только для SIT).
    """
    if model == "ideal":
        return None
    
    A, B = dh_constants(T, eps)
    
    if model == "debye_huckel":
        def f(I, z, m=None):
            sI = math.sqrt(max(I, 0.0))
            return -LN10 * A * np.asarray(z) ** 2 * sI / (1.0 + B * ion_size_A * sI)
        return f
        
    if model in ("davies", "pitzer"):
        def f(I, z, m=None):
            sI = math.sqrt(max(I, 0.0))
            return -LN10 * A * np.asarray(z) ** 2 * (sI / (1.0 + sI) - 0.3 * I)
        return f
        
    if model == "sit":
        if species_list is None or db is None:
            raise ValueError("Для модели SIT необходимо передать species_list и db")
            
        sit_matrix = make_sit_matrix(species_list, db)
        
        def f(I, z, m=None):
            if m is None:
                raise ValueError("Для модели SIT необходим массив моляльностей m")
            
            sI = math.sqrt(max(I, 0.0))
            # Первое слагаемое (Дебай-Хюккель)
            dh_term = -LN10 * A * np.asarray(z) ** 2 * sI / (1.0 + 1.5 * sI)
            
            # Второе слагаемое (SIT: сумма по j epsilon(i,j)*m_j)
            # m - вектор моляльностей всех частиц
            sit_term = LN10 * (sit_matrix @ m)
            
            return dh_term + sit_term
        return f

    raise ValueError(f"Неизвестная модель активности: {model}")


def validity_warning(model: str, I: float) -> str | None:
    limits = {"ideal": 0.1, "debye_huckel": 0.15, "davies": 0.6, "sit": 6.0, "pitzer": 20.0}
    max_I = limits.get(model, 0.6)
    if I > max_I:
        return f"Ионная сила {I:.2f} М выше области применимости модели {model.upper()} (~{max_I} М); расчет может быть неточным"
    return None