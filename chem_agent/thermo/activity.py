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


PITZER_B = 1.2  # кг^0.5 моль^-0.5, универсальная константа Pitzer


def _pitzer_g(x: np.ndarray) -> np.ndarray:
    """g(x) = 2[1 - (1 + x) e^-x] / x^2; g(0) = 1."""
    x = np.where(x > 1e-12, x, 1e-12)
    return 2.0 * (1.0 - (1.0 + x) * np.exp(-x)) / x ** 2


def _pitzer_gp(x: np.ndarray) -> np.ndarray:
    """g'(x) = -2[1 - (1 + x + x^2/2) e^-x] / x^2; g'(0) = 0."""
    x = np.where(x > 1e-12, x, 1e-12)
    return -2.0 * (1.0 - (1.0 + x + 0.5 * x ** 2) * np.exp(-x)) / x ** 2


def make_pitzer_fn(species_list, db, A_log10: float) -> Callable:
    """Модель Pitzer (Harvie, Moller, Weare 1984) для смеси ионов, ln(gamma) на моляльной шкале.

    ln g_M = z_M^2 F + SUM_a m_a (2 B_Ma + Z C_Ma) + SUM_c m_c 2 theta_Mc + |z_M| SUM_c SUM_a m_c m_a C_ca
    F = f_gamma + SUM_c SUM_a m_c m_a B'_ca
    f_gamma = -A_phi [sqrt(I) / (1 + b sqrt(I)) + (2/b) ln(1 + b sqrt(I))],  b = 1.2
    B = beta0 + beta1 g(a1 sqrt(I)) + beta2 g(a2 sqrt(I)),  B' = [beta1 g'(a1 sqrt(I)) + beta2 g'(a2 sqrt(I))] / I
    a1 = 2.0, beta2 = 0 для пар с однозарядным ионом; a1 = 1.4, a2 = 12 для пар 2:2 и выше.
    C = C_phi / (2 sqrt|z_M z_X|).
    Анион симметрично. Нейтральные частицы: ln g = 0 (параметров lambda нет).
    Не учтены: несимметричное смешение E-theta, тройные psi, зависимость параметров от T.
    Пары без параметров в pitzer_parameters дают только член Debye-Huckel f_gamma.
    """
    formulas = [s.formula for s in species_list]
    zs = np.array([s.charge for s in species_list], dtype=float)
    n = len(formulas)
    b0, b1, b2 = np.zeros((n, n)), np.zeros((n, n)), np.zeros((n, n))
    a1, a2 = np.full((n, n), 2.0), np.full((n, n), 12.0)
    C, theta = np.zeros((n, n)), np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j or zs[i] == 0 or zs[j] == 0:
                continue
            p = db.get_pitzer(formulas[i], formulas[j])
            if not p:
                continue
            if zs[i] * zs[j] < 0:
                b0[i, j], b1[i, j], b2[i, j] = p["beta0"], p["beta1"], p["beta2"] or 0.0
                if abs(zs[i]) >= 2 and abs(zs[j]) >= 2:
                    a1[i, j] = 1.4
                C[i, j] = (p["C_phi"] or 0.0) / (2.0 * math.sqrt(abs(zs[i] * zs[j])))
            else:
                theta[i, j] = p["theta"] or 0.0
    A_phi = A_log10 * LN10 / 3.0
    absz = np.abs(zs)

    def f(I, z, m=None):
        if m is None:
            raise ValueError("Для модели Pitzer необходим массив моляльностей m")
        m = np.asarray(m, dtype=float)
        I = 0.5 * float(np.dot(m, zs ** 2))
        if I <= 0.0:
            return np.zeros(n)
        sI = math.sqrt(I)
        Z = float(np.dot(m, absz))
        f_gamma = -A_phi * (sI / (1.0 + PITZER_B * sI) + 2.0 / PITZER_B * math.log1p(PITZER_B * sI))
        Bm = b0 + b1 * _pitzer_g(a1 * sI) + b2 * _pitzer_g(a2 * sI)
        Bp = (b1 * _pitzer_gp(a1 * sI) + b2 * _pitzer_gp(a2 * sI)) / I
        F = f_gamma + 0.5 * m @ Bp @ m
        CC = 0.5 * m @ C @ m
        out = zs ** 2 * F + (2.0 * Bm + Z * C) @ m + 2.0 * theta @ m + absz * CC
        out[zs == 0] = 0.0
        return out
    return f


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
        
    if model == "pitzer":
        if species_list is None or db is None:
            raise ValueError("Для модели Pitzer необходимо передать species_list и db")
        return make_pitzer_fn(species_list, db, A)

    if model == "davies":
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