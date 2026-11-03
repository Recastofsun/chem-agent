"""Activation barriers: only from the user or from well-established reaction classes.
No ML transition-state model is shipped (none exists that is reliable offline for arbitrary
reactions). Class values are literature orders of magnitude, labelled as such.

W-17: Диффузионный контроль — комбинирование k_act и k_diff через формулу
      1/k_obs = 1/k_act + 1/k_diff. Для быстрых реакций (протонный перенос, осаждение)
      лимитирует диффузия, для медленных — активация.
"""
from __future__ import annotations

from dataclasses import dataclass
from . import eyring

# Diffusion-controlled proton transfer H+ + OH- -> H2O: k = 1.4e11 M^-1 s^-1 at 25 C (Eigen, 1964).
PROTON_TRANSFER_K = 1.4e11

# Типичная диффузионная константа для ионов в воде при 25°C
# (D ~ 1e-9 м²/с, R ~ 5 Å): k_diff ~ 7.5e9 M^-1 s^-1
TYPICAL_ION_DIFFUSION_K = 7.5e9


@dataclass
class BarrierInfo:
    barrier_kJ_mol: float | None
    sigma_kJ: float | None
    rate_constant: float | None
    order: int
    model: str
    note: str


def classify(analysis_kinds: set[str], ionic_consumed: set[str]) -> str:
    if "H+" in ionic_consumed and "OH-" in ionic_consumed:
        return "proton_transfer"
    if "H+" in ionic_consumed or "OH-" in ionic_consumed:
        return "acid_base"
    if "precipitate" in analysis_kinds:
        return "precipitation"
    return "other"


def resolve(user: dict | None, T: float, reaction_class: str,
            catalyst: dict | None = None,
            barrier_params: dict | None = None) -> BarrierInfo:
    """
    Разрешение барьера реакции с учётом температурной зависимости (W-13) и
    диффузионного контроля (W-17).
    
    barrier_params — результат db.get_barrier(reaction_key), dict с полями:
        ea_kj_mol, t_ref, dh_act_kj_mol, ds_act_j_mol_k, t_ref_2, ea_t2_kj_mol
    """
    user = user or {}
    cat_barrier = (catalyst or {}).get("barrier_kJ_mol")
    
    # Катализатор имеет высший приоритет
    if cat_barrier is not None:
        b = float(cat_barrier)
        s = float((catalyst or {}).get("barrier_uncertainty", 5.0))
        k_act = eyring.rate_constant(b, T)
        return BarrierInfo(b, s, k_act, int(user.get("order", 2)),
                          "Eyring (барьер с катализатором, задан пользователем)",
                          "Катализатор не меняет равновесие; влияет только на скорость через заданный барьер")
    
    # Явно заданный пользователем барьер
    if user.get("barrier_kJ_mol") is not None:
        b = float(user["barrier_kJ_mol"])
        s = float(user.get("uncertainty", 5.0))
        k_act = eyring.rate_constant(b, T)
        return BarrierInfo(b, s, k_act, int(user.get("order", 2)),
                          "Eyring (барьер задан пользователем)", " ")
    
    # W-13: Используем параметры из БД (db.get_barrier возвращает dict)
    if barrier_params is not None:
        # Приоритет 1: полное уравнение Эйринга (ΔH‡, ΔS‡)
        if (barrier_params.get("dh_act_kj_mol") is not None and 
            barrier_params.get("ds_act_j_mol_k") is not None):
            k_act = eyring.rate_constant_eyring(
                barrier_params["dh_act_kj_mol"],
                barrier_params["ds_act_j_mol_k"],
                T
            )
            # W-17: Комбинирование с диффузионным контролем для быстрых реакций
            if reaction_class in ("proton_transfer", "acid_base", "precipitation"):
                k_diff = _get_diffusion_k(reaction_class, T)
                k_obs = eyring.combined_rate_constant(k_act, k_diff)
                return BarrierInfo(
                    barrier_params["dh_act_kj_mol"],
                    5.0,
                    k_obs, 2,
                    "Eyring + diffusion (ΔH‡, ΔS‡ из БД, W-13+W-17)",
                    f"ΔH‡={barrier_params['dh_act_kj_mol']:.2f} кДж/моль, "
                    f"k_act={k_act:.2e}, k_diff={k_diff:.2e}, k_obs={k_obs:.2e}"
                )
            return BarrierInfo(
                barrier_params["dh_act_kj_mol"],
                5.0,
                k_act, 2,
                "Eyring (ΔH‡, ΔS‡ из БД, W-13)",
                f"ΔH‡={barrier_params['dh_act_kj_mol']:.2f} кДж/моль, "
                f"ΔS‡={barrier_params['ds_act_j_mol_k']:.2f} Дж/(моль·К)"
            )
        
        # Приоритет 2: двухточечная интерполяция
        if (barrier_params.get("ea_t2_kj_mol") is not None and
            barrier_params.get("t_ref_2") is not None and
            barrier_params.get("ea_kj_mol") is not None and
            barrier_params.get("t_ref") is not None):
            ea_T = eyring.ea_at_temperature(
                barrier_params["ea_kj_mol"], barrier_params["t_ref"],
                barrier_params["ea_t2_kj_mol"], barrier_params["t_ref_2"],
                T
            )
            k_act = eyring.rate_constant(ea_T, T)
            if reaction_class in ("proton_transfer", "acid_base", "precipitation"):
                k_diff = _get_diffusion_k(reaction_class, T)
                k_obs = eyring.combined_rate_constant(k_act, k_diff)
                return BarrierInfo(
                    ea_T, 5.0, k_obs, 2,
                    "Eyring + diffusion (интерполяция Ea, W-13+W-17)",
                    f"Ea({T:.0f}K)={ea_T:.2f} кДж/моль, k_act={k_act:.2e}, k_diff={k_diff:.2e}"
                )
            return BarrierInfo(
                ea_T, 5.0, k_act, 2,
                "Eyring (интерполяция Ea, W-13)",
                f"Ea({T:.0f}K)={ea_T:.2f} кДж/моль"
            )
        
        # Приоритет 3: старая модель (константа Ea)
        if barrier_params.get("ea_kj_mol") is not None:
            b = barrier_params["ea_kj_mol"]
            k_act = eyring.rate_constant(b, T)
            t_ref = barrier_params.get("t_ref")
    
            # W-17: Комбинирование с диффузионным контролем для быстрых реакций
            if reaction_class in ("proton_transfer", "acid_base", "precipitation"):
                k_diff = _get_diffusion_k(reaction_class, T)
                k_obs = eyring.combined_rate_constant(k_act, k_diff)
                note = f"Ea={b:.2f} кДж/моль"
                if t_ref is not None:
                    note += f" (при T_ref={t_ref:.0f}K)"
                note += f", k_act={k_act:.2e}, k_diff={k_diff:.2e}, k_obs={k_obs:.2e}"
                return BarrierInfo(b, 5.0, k_obs, 2, "Eyring + diffusion (Ea из БД, W-13+W-17)", note)
    
            note = f"Ea={b:.2f} кДж/моль"
            if t_ref is not None:
                note += f" (при T_ref={t_ref:.0f}K)"
            return BarrierInfo(b, 5.0, k_act, 2, "Eyring (Ea из БД)", note)
    
    # Стандартные классы реакций
    if reaction_class == "proton_transfer":
        # Протонный перенос: диффузионный контроль (Eigen, 1964)
        # k_act очень большой (барьер ~0), поэтому k_obs ≈ k_diff
        return BarrierInfo(
            eyring.barrier_from_rate(PROTON_TRANSFER_K, T),
            2.0,
            PROTON_TRANSFER_K, 2,
            "diffusion-limit (Eigen)",
            "Нейтрализация H+ + OH- ограничена диффузией, k ≈ 1,4·10¹¹ М⁻¹·с⁻¹ (25 °C)"
        )
    
    if reaction_class == "acid_base":
        # Кислотно-основные реакции: обычно быстрые, диффузионный контроль
        k_diff = TYPICAL_ION_DIFFUSION_K
        return BarrierInfo(
            None, None, k_diff, 2,
            "diffusion-limit (типичный для ионов)",
            f"Перенос протона обычно быстрый, k_diff ≈ {k_diff:.1e} М⁻¹·с⁻¹"
        )
    
    if reaction_class == "precipitation":
        # Осаждение: диффузионный контроль + зарождение кристаллов
        k_diff = TYPICAL_ION_DIFFUSION_K
        return BarrierInfo(
            None, None, k_diff, 2,
            "diffusion-limit (осаждение)",
            f"Осаждение ограничено диффузией ионов, k_diff ≈ {k_diff:.1e} М⁻¹·с⁻¹; "
            "зарождение кристаллов может добавлять кинетический барьер"
        )
    
    return BarrierInfo(None, None, None, 2, "неизвестно",
                      "Барьер не задан; предсказание кинетики без данных не делается. "
                      "Задайте options.kinetics.barrier_kJ_mol")


def _get_diffusion_k(reaction_class: str, T: float) -> float:
    """
    Возвращает типичную диффузионную константу для класса реакции.
    
    Args:
        reaction_class: класс реакции
        T: температура, K
    
    Returns:
        k_diff в M^-1 s^-1
    """
    if reaction_class == "proton_transfer":
        return PROTON_TRANSFER_K
    elif reaction_class in ("acid_base", "precipitation"):
        return TYPICAL_ION_DIFFUSION_K
    else:
        # Для остальных реакций диффузионный контроль не применяем
        return float('inf')  # k_diff = inf → k_obs = k_act