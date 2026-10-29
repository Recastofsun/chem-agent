"""Activation barriers: only from the user or from well-established reaction classes.

No ML transition-state model is shipped (none exists that is reliable offline for arbitrary
reactions). Class values are literature orders of magnitude, labelled as such.
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


def resolve(user: dict | None, T: float, reaction_class: str, catalyst: dict | None = None) -> BarrierInfo:
    user = user or {}
    cat_barrier = (catalyst or {}).get("barrier_kJ_mol")
    if cat_barrier is not None:
        b = float(cat_barrier)
        s = float((catalyst or {}).get("barrier_uncertainty", 5.0))
        return BarrierInfo(b, s, eyring.rate_constant(b, T), int(user.get("order", 2)),
                           "Eyring (барьер с катализатором, задан пользователем)",
                           "Катализатор не меняет равновесие; влияет только на скорость через заданный барьер")
    if user.get("barrier_kJ_mol") is not None:
        b = float(user["barrier_kJ_mol"])
        s = float(user.get("uncertainty", 5.0))
        return BarrierInfo(b, s, eyring.rate_constant(b, T), int(user.get("order", 2)),
                           "Eyring (барьер задан пользователем)", "")
    if reaction_class == "proton_transfer":
        k = PROTON_TRANSFER_K
        return BarrierInfo(eyring.barrier_from_rate(k, T), 2.0, k, 2, "diffusion-limit (Eigen)",
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
