"""Activation barriers: only from the user or from well-established reaction classes.
No ML transition-state model is shipped (none exists that is reliable offline for arbitrary
reactions). Class values are literature orders of magnitude, labelled as such.

W-13: Добавлена поддержка температурной зависимости Ea(T) через:
- Полное уравнение Эйринга (ΔH‡, ΔS‡)
- Двухточечную интерполяцию Ea
- Старую модель (константа Ea)
"""
from __future__ import annotations

from dataclasses import dataclass
from . import eyring

# Diffusion-controlled proton transfer H+ + OH- -> H2O: k = 1.4e11 M^-1 s^-1 at 25 C (Eigen, 1964).
PROTON_TRANSFER_K = 1.4e11


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
    Разрешение барьера реакции с учётом температурной зависимости (W-13).
    
    barrier_params — результат db.get_barrier(reaction_key), dict с полями:
        ea_kj_mol, t_ref, dh_act_kj_mol, ds_act_j_mol_k, t_ref_2, ea_t2_kj_mol
    """
    user = user or {}
    cat_barrier = (catalyst or {}).get("barrier_kJ_mol")
    
    # Катализатор имеет высший приоритет
    if cat_barrier is not None:
        b = float(cat_barrier)
        s = float((catalyst or {}).get("barrier_uncertainty", 5.0))
        return BarrierInfo(b, s, eyring.rate_constant(b, T), int(user.get("order", 2)),
                          "Eyring (барьер с катализатором, задан пользователем)",
                          "Катализатор не меняет равновесие; влияет только на скорость через заданный барьер")
    
    # Явно заданный пользователем барьер
    if user.get("barrier_kJ_mol") is not None:
        b = float(user["barrier_kJ_mol"])
        s = float(user.get("uncertainty", 5.0))
        return BarrierInfo(b, s, eyring.rate_constant(b, T), int(user.get("order", 2)),
                          "Eyring (барьер задан пользователем)", " ")
    
    # W-13: Используем параметры из БД (db.get_barrier возвращает dict)
    if barrier_params is not None:
        # Приоритет 1: полное уравнение Эйринга (ΔH‡, ΔS‡)
        if (barrier_params.get("dh_act_kj_mol") is not None and 
            barrier_params.get("ds_act_j_mol_k") is not None):
            k = eyring.rate_constant_eyring(
                barrier_params["dh_act_kj_mol"],
                barrier_params["ds_act_j_mol_k"],
                T
            )
            return BarrierInfo(
                barrier_params["dh_act_kj_mol"],
                5.0,
                k, 2,
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
            k = eyring.rate_constant(ea_T, T)
            return BarrierInfo(
                ea_T, 5.0, k, 2,
                "Eyring (интерполяция Ea, W-13)",
                f"Ea({T:.0f}K)={ea_T:.2f} кДж/моль"
            )
        
        # Приоритет 3: старая модель (константа Ea)
        if barrier_params.get("ea_kj_mol") is not None:
            b = barrier_params["ea_kj_mol"]
            k = eyring.rate_constant(b, T)
            t_ref = barrier_params.get("t_ref")
            note = f"Ea={b:.2f} кДж/моль"
            if t_ref is not None:
                note += f" (при T_ref={t_ref:.0f}K)"
            return BarrierInfo(b, 5.0, k, 2, "Eyring (Ea из БД)", note)
    
    # Стандартные классы реакций (без изменений)
    if reaction_class == "proton_transfer":
        k = PROTON_TRANSFER_K
        return BarrierInfo(eyring.barrier_from_rate(k, T), 2.0, k, 2, 
                          "diffusion-limit (Eigen)",
                          "Нейтрализация H+ + OH- ограничена диффузией, k ≈ 1,4·10¹¹ М⁻¹·с⁻¹ (25 °C)")
    
    if reaction_class == "acid_base":
        return BarrierInfo(None, None, None, 2, "класс: кислотно-основная",
                          "Перенос протона обычно быстрый (мс и быстрее), но константа для этой пары "
                          "в базе не задана - неизвестно")
    
    if reaction_class == "precipitation":
        return BarrierInfo(None, None, None, 2, "класс: осаждение",
                          "Осаждение обычно идет за секунды-минуты и лимитируется зарождением кристаллов; "
                          "константа скорости неизвестна")
    
    return BarrierInfo(None, None, None, 2, "неизвестно",
                      "Барьер не задан; предсказание кинетики без данных не делается. "
                      "Задайте options.kinetics.barrier_kJ_mol")