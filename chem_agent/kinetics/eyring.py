"""Eyring equation (transition state theory) — расширено для W-13."""
from __future__ import annotations
import math

KB = 1.380649e-23      # J/K
H_PLANCK = 6.62607015e-34
R_J = 8.314462618      # J/(mol K)
R_KJ = 8.314462618e-3  # kJ/(mol K)


def rate_constant(barrier_kJ_mol: float, T: float, kappa: float = 1.0) -> float:
    """k = kappa * kB*T/h * exp(-dG_act / RT), s^-1 (first order) or M^-1 s^-1 with c0 = 1 M."""
    return kappa * KB * T / H_PLANCK * math.exp(-barrier_kJ_mol * 1000.0 / (R_J * T))


def barrier_from_rate(k: float, T: float) -> float:
    return -R_J * T * math.log(k * H_PLANCK / (KB * T)) / 1000.0


def rate_constant_sigma(barrier_kJ_mol: float, sigma_kJ: float, T: float) -> tuple[float, float]:
    """Return (k, relative factor) for 1-sigma barrier uncertainty: k in [k/f, k*f]."""
    k = rate_constant(barrier_kJ_mol, T)
    f = math.exp(sigma_kJ * 1000.0 / (R_J * T))
    return k, f


# ============================================================================
# W-13: Расширенные модели температурной зависимости
# ============================================================================

def rate_constant_eyring(dh_act_kJ_mol: float, ds_act_J_mol_K: float, 
                         T: float, kappa: float = 1.0) -> float:
    """
    Полное уравнение Эйринга через ΔH‡ и ΔS‡:
        k = κ · (kB·T/h) · exp(ΔS‡/R) · exp(-ΔH‡/(R·T))
    
    Args:
        dh_act_kJ_mol: энтальпия активации, кДж/моль
        ds_act_J_mol_K: энтропия активации, Дж/(моль·К)
        T: температура, K
        kappa: коэффициент прохождения (по умолчанию 1.0)
    
    Returns:
        Константа скорости, s^-1 (для первого порядка) или M^-1·s^-1
    """
    prefactor = kappa * KB * T / H_PLANCK
    entropy_term = math.exp(ds_act_J_mol_K / R_J)
    enthalpy_term = math.exp(-dh_act_kJ_mol * 1000.0 / (R_J * T))
    return prefactor * entropy_term * enthalpy_term


def ea_at_temperature(ea1: float, t1: float, ea2: float, t2: float, T: float) -> float:
    """
    Линейная интерполяция Ea между двумя опорными температурами.
        Ea(T) = Ea1 + (Ea2 - Ea1) / (T2 - T1) · (T - T1)
    
    Args:
        ea1, ea2: энергии активации при t1 и t2, кДж/моль
        t1, t2: опорные температуры, K
        T: целевая температура, K
    
    Returns:
        Ea при температуре T, кДж/моль
    """
    if abs(t2 - t1) < 1e-6:
        return ea1
    return ea1 + (ea2 - ea1) / (t2 - t1) * (T - t1)


def rate_constant_from_ea_interp(ea1: float, t1: float, ea2: float, t2: float, 
                                  T: float, kappa: float = 1.0) -> float:
    """
    Константа скорости через интерполированное Ea(T) и уравнение Эйринга.
    """
    ea_T = ea_at_temperature(ea1, t1, ea2, t2, T)
    return rate_constant(ea_T, T, kappa)


def dh_ds_from_ea(ea_kJ_mol: float, t_ref: float) -> tuple[float, float]:
    """
    Пересчёт Ea при T_ref в ΔH‡ и ΔS‡ так, чтобы rate_constant_eyring(dh, ds, t_ref)
    давал точно rate_constant(ea, t_ref).
    
    Используется приближение ΔH‡ ≈ Ea (без поправки RT, которая малa для реакций в растворе).
    ΔS‡ вычисляется из условия воспроизведения k.
    """
    k_ref = rate_constant(ea_kJ_mol, t_ref)
    dh_act = ea_kJ_mol  # приближение: ΔH‡ ≈ Ea
    
    # Из уравнения Эйринга: k = (kB*T/h) * exp(ΔS‡/R) * exp(-ΔH‡/(R*T))
    # Отсюда: ΔS‡ = R * ln(k * h / (kB * T)) + ΔH‡/T
    ds_act = R_J * math.log(k_ref * H_PLANCK / (KB * t_ref)) + dh_act * 1000.0 / t_ref
    
    return dh_act, ds_act


def ea_from_dh_ds(dh_act_kJ_mol: float, ds_act_J_mol_K: float, T: float) -> float:
    """
    Обратная задача: вычислить эффективное Ea при температуре T из ΔH‡ и ΔS‡.
    Полезно для сравнения с литературными значениями Ea.
    
    Из уравнения Эйринга:
        k = (kB·T/h) · exp(ΔS‡/R) · exp(-ΔH‡/(R·T))
    Приравниваем к Arrhenius: k = A · exp(-Ea/(R·T))
    Отсюда: Ea = ΔH‡ + R·T - R·T·ln(kB·T/h · exp(ΔS‡/R) / A)
    
    Для стандартного случая (A = kB·T/h · exp(ΔS‡/R)):
        Ea ≈ ΔH‡ + R·T
    """
    return dh_act_kJ_mol + R_KJ * T