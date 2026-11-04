"""
Мембранный транспорт в электрохимической ячейке (уравнение Нернста-Планка).

Для тонкой мембраны со стационарным профилем концентрации:
J_i = (D_i/δ) * (C_i^anode - C_i^cathode) - (z_i * F * D_i / (R * T * δ)) * C_i_avg * Δφ

Селективность:
- "cation_exchange" (CEM): пропускает только катионы (z > 0)
- "anion_exchange" (AEM): пропускает только анионы (z < 0)
- "bipolar" (BPM): пропускает H+ и OH-
- "porous" (non_selective): пропускает все ионы
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

F = 96485.332
R_GAS = 8.31446


def water_viscosity(T: float) -> float:
    """Динамическая вязкость воды (Па·с), корреляция Vogel."""
    A = 2.414e-5
    B = 247.8
    C = 140.0
    return A * 10**(B / (T - C))


@dataclass
class Membrane:
    """Параметры мембраны."""
    type: str = "cation_exchange"  # "cation_exchange", "anion_exchange", "bipolar", "porous"
    area_m2: float = 0.01
    thickness_m: float = 1e-4
    permselectivity: float = 0.95
    water_transport: float = 0.0


# Коэффициенты диффузии в воде при 25°C (м²/с)
DIFFUSION_COEFFICIENTS_298 = {
    "H+": 9.3e-9,
    "OH-": 5.3e-9,
    "Na+": 1.3e-9,
    "K+": 1.9e-9,
    "Cl-": 2.0e-9,
    "SO4-2": 1.0e-9,
    "NO3-": 1.9e-9,
    "Ca+2": 0.8e-9,
    "Mg+2": 0.7e-9,
    "Cu+2": 0.7e-9,
    "Zn+2": 0.7e-9,
    "Fe+2": 0.7e-9,
    "Fe+3": 0.6e-9,
}


def diffusion_at_temperature(ion_formula: str, T: float) -> float:
    """Коэффициент диффузии при температуре T (уравнение Стокса-Эйнштейна)."""
    D_298 = DIFFUSION_COEFFICIENTS_298.get(ion_formula, 1e-9)
    eta_298 = water_viscosity(298.15)
    eta_T = water_viscosity(T)
    return D_298 * (T / 298.15) * (eta_298 / eta_T)


def ion_flux(
    ion_formula: str,
    charge: int,
    concentration_anode: float,
    concentration_cathode: float,
    delta_phi: float,
    T: float,
    membrane: Membrane,
) -> float:
    """
    Поток иона через мембрану (моль/м²·с) по уравнению Нернста-Планка.
    """
    D = diffusion_at_temperature(ion_formula, T)
    C_avg = 0.5 * (concentration_anode + concentration_cathode)
    dC = concentration_anode - concentration_cathode
    
    J_diff = (D / membrane.thickness_m) * dC
    J_mig = -(charge * F * D / (R_GAS * T * membrane.thickness_m)) * C_avg * delta_phi
    
    # Селективность
    selectivity = _selectivity(membrane.type, charge, ion_formula, membrane.permselectivity)
    
    return (J_diff + J_mig) * selectivity


def _selectivity(membrane_type: str, charge: int, ion_formula: str, permselectivity: float) -> float:
    """Коэффициент пропускания иона через мембрану."""
    # Маппинг сокращений
    type_map = {
        "CEM": "cation_exchange",
        "AEM": "anion_exchange",
        "BPM": "bipolar",
        "non_selective": "porous"
    }
    membrane_type = type_map.get(membrane_type, membrane_type)
    
    if membrane_type == "porous":
        return 1.0
    elif membrane_type == "cation_exchange":
        return permselectivity if charge > 0 else (1.0 - permselectivity)
    elif membrane_type == "anion_exchange":
        return permselectivity if charge < 0 else (1.0 - permselectivity)
    elif membrane_type == "bipolar":
        if ion_formula in ("H+", "OH-"):
            return permselectivity
        return 1.0 - permselectivity
    return 1.0


def update_chambers(
    anode_concentrations: Dict[str, float],
    cathode_concentrations: Dict[str, float],
    charges: Dict[str, int],
    delta_phi: float,
    T: float,
    membrane: Membrane,
    duration_s: float,
    anode_volume_m3: float,
    cathode_volume_m3: float,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    Обновить концентрации в камерах после мембранного транспорта.
    Для porous мембраны сохраняет электронейтральность.
    """
    new_anode = dict(anode_concentrations)
    new_cathode = dict(cathode_concentrations)
    ion_transfers = {}
    
    all_ions = set(anode_concentrations.keys()) | set(cathode_concentrations.keys())
    
    if membrane.type == "porous":
        # Для пористой мембраны: нормализуем потоки для сохранения электронейтральности
        cation_fluxes = {}
        anion_fluxes = {}
        
        for ion in all_ions:
            z = charges.get(ion, 0)
            C_an = anode_concentrations.get(ion, 0.0)
            C_cat = cathode_concentrations.get(ion, 0.0)
            J = ion_flux(ion, z, C_an, C_cat, delta_phi, T, membrane)
            
            if z > 0:
                cation_fluxes[ion] = J
            elif z < 0:
                anion_fluxes[ion] = J
        
        # Нормализуем: суммарный ток катионов = суммарному току анионов
        total_cation_J = sum(cation_fluxes.values())
        total_anion_J = sum(anion_fluxes.values())
        
        # Если токи не равны, масштабируем меньший
        if abs(total_cation_J) > abs(total_anion_J) and abs(total_anion_J) > 1e-12:
            scale = total_anion_J / total_cation_J
            for ion in cation_fluxes:
                cation_fluxes[ion] *= scale
        elif abs(total_anion_J) > abs(total_cation_J) and abs(total_cation_J) > 1e-12:
            scale = total_cation_J / total_anion_J
            for ion in anion_fluxes:
                anion_fluxes[ion] *= scale
        
        # Применяем потоки
        for ion, J in {**cation_fluxes, **anion_fluxes}.items():
            z = charges.get(ion, 0)
            C_an = anode_concentrations.get(ion, 0.0)
            C_cat = cathode_concentrations.get(ion, 0.0)
            n_transfer = J * membrane.area_m2 * duration_s
            
            new_anode[ion] = max(0.0, C_an - n_transfer / anode_volume_m3)
            new_cathode[ion] = C_cat + n_transfer / cathode_volume_m3
            
            if abs(n_transfer) > 1e-12:
                ion_transfers[ion] = n_transfer
    else:
        # Для селективных мембран: каждый ион переносится независимо
        for ion in all_ions:
            z = charges.get(ion, 0)
            C_an = anode_concentrations.get(ion, 0.0)
            C_cat = cathode_concentrations.get(ion, 0.0)
            J = ion_flux(ion, z, C_an, C_cat, delta_phi, T, membrane)
            
            n_transfer = J * membrane.area_m2 * duration_s
            
            new_anode[ion] = max(0.0, C_an - n_transfer / anode_volume_m3)
            new_cathode[ion] = C_cat + n_transfer / cathode_volume_m3
            
            if abs(n_transfer) > 1e-12:
                ion_transfers[ion] = n_transfer
    
    return new_anode, new_cathode, ion_transfers