"""Пул 100 реакций (ТЗ п. 13): data/pool_100.json.

Ожидания - учебная неорганическая химия (Глинка, Ахметов, Cotton & Wilkinson), не подгонка под ядро.
Количества подобраны так, чтобы фаза продукта в ожидании была физически верной при 1 л воды:
газ со стрелкой - только если его больше растворимости (CO2 > 0,034 моль/л, H2, O2, N2 - почти всегда),
хорошо растворимые газы (NH3, SO2, HCl) в 1 л воды при 298 K остаются растворенными - без стрелки.
Формат уравнения: "a A + b B -> c C↓ + d D↑", ↓ - твердое, ↑ - газ, без метки - раствор/жидкость.
Запуск: python scripts/build_pool.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "pool_100.json"


def R(f, n, ph="aq"):
    return {"formula": f, "moles": n, "phase": ph}


W = {"solvent": "water", "volume_L": 1.0}
DRY = {"solvent": "none", "volume_L": 1.0}

POOL = [
    # --- нейтрализация (15)
    ("n01", "нейтрализация", [R("HCl", .1), R("NaOH", .1)], W, "NaCl", "HCl + NaOH -> NaCl + H2O"),
    ("n02", "нейтрализация", [R("H2SO4", .05), R("NaOH", .1)], W, "Na2SO4", "H2SO4 + 2 NaOH -> Na2SO4 + 2 H2O"),
    ("n03", "нейтрализация", [R("HNO3", .1), R("KOH", .1)], W, "KNO3", "HNO3 + KOH -> KNO3 + H2O"),
    ("n04", "нейтрализация", [R("HCl", .02), R("Ca(OH)2", .01)], W, "CaCl2", "2 HCl + Ca(OH)2 -> CaCl2 + 2 H2O"),
    ("n05", "нейтрализация", [R("H3PO4", .05), R("NaOH", .15)], W, "Na3PO4", "H3PO4 + 3 NaOH -> Na3PO4 + 3 H2O"),
    ("n06", "нейтрализация", [R("H3PO4", .1), R("NaOH", .1)], W, "NaH2PO4", "H3PO4 + NaOH -> NaH2PO4 + H2O"),
    ("n07", "нейтрализация", [R("HBr", .1), R("KOH", .1)], W, "KBr", "HBr + KOH -> KBr + H2O"),
    ("n08", "нейтрализация", [R("HCl", .1), R("NH3", .1)], W, "NH4Cl", "HCl + NH3 -> NH4Cl"),
    ("n09", "нейтрализация", [R("H2SO4", .05), R("NH3", .1)], W, "(NH4)2SO4", "H2SO4 + 2 NH3 -> (NH4)2SO4"),
    ("n10", "нейтрализация", [R("HNO3", .1), R("Ba(OH)2", .05)], W, "Ba(NO3)2", "2 HNO3 + Ba(OH)2 -> Ba(NO3)2 + 2 H2O"),
    ("n11", "нейтрализация", [R("H2SO4", .05), R("Mg(OH)2", .05, "s")], W, "MgSO4", "H2SO4 + Mg(OH)2 -> MgSO4 + 2 H2O"),
    ("n12", "нейтрализация", [R("HCl", .1), R("Cu(OH)2", .05, "s")], W, "CuCl2", "2 HCl + Cu(OH)2 -> CuCl2 + 2 H2O"),
    ("n13", "нейтрализация", [R("HCl", .1), R("ZnO", .05, "s")], W, "ZnCl2", "2 HCl + ZnO -> ZnCl2 + H2O"),
    ("n14", "нейтрализация", [R("HNO3", .1), R("CaO", .05, "s")], W, "Ca(NO3)2", "2 HNO3 + CaO -> Ca(NO3)2 + H2O"),
    ("n15", "нейтрализация", [R("HClO4", .1), R("LiOH", .1)], W, "LiClO4", "HClO4 + LiOH -> LiClO4 + H2O"),
    # --- осаждение (20)
    ("p01", "осаждение", [R("BaCl2", .05), R("Na2SO4", .05)], W, "BaSO4", "BaCl2 + Na2SO4 -> BaSO4↓ + 2 NaCl"),
    ("p02", "осаждение", [R("AgNO3", .05), R("NaCl", .05)], W, "AgCl", "AgNO3 + NaCl -> AgCl↓ + NaNO3"),
    ("p03", "осаждение", [R("AgNO3", .05), R("KBr", .05)], W, "AgBr", "AgNO3 + KBr -> AgBr↓ + KNO3"),
    ("p04", "осаждение", [R("AgNO3", .05), R("KI", .05)], W, "AgI", "AgNO3 + KI -> AgI↓ + KNO3"),
    ("p05", "осаждение", [R("Pb(NO3)2", .05), R("KI", .1)], W, "PbI2", "Pb(NO3)2 + 2 KI -> PbI2↓ + 2 KNO3"),
    ("p06", "осаждение", [R("CaCl2", .05), R("Na2CO3", .05)], W, "CaCO3", "CaCl2 + Na2CO3 -> CaCO3↓ + 2 NaCl"),
    ("p07", "осаждение", [R("CuSO4", .05), R("NaOH", .1)], W, "Cu(OH)2", "CuSO4 + 2 NaOH -> Cu(OH)2↓ + Na2SO4"),
    ("p08", "осаждение", [R("FeCl3", .05), R("NaOH", .15)], W, "Fe(OH)3", "FeCl3 + 3 NaOH -> Fe(OH)3↓ + 3 NaCl"),
    ("p09", "осаждение", [R("FeSO4", .05), R("NaOH", .1)], W, "Fe(OH)2", "FeSO4 + 2 NaOH -> Fe(OH)2↓ + Na2SO4"),
    ("p10", "осаждение", [R("MgCl2", .05), R("NaOH", .1)], W, "Mg(OH)2", "MgCl2 + 2 NaOH -> Mg(OH)2↓ + 2 NaCl"),
    ("p11", "осаждение", [R("CaCl2", .03), R("Na3PO4", .02)], W, "Ca3(PO4)2", "3 CaCl2 + 2 Na3PO4 -> Ca3(PO4)2↓ + 6 NaCl"),
    ("p12", "осаждение", [R("Pb(NO3)2", .05), R("Na2SO4", .05)], W, "PbSO4", "Pb(NO3)2 + Na2SO4 -> PbSO4↓ + 2 NaNO3"),
    ("p13", "осаждение", [R("BaCl2", .05), R("Na2CO3", .05)], W, "BaCO3", "BaCl2 + Na2CO3 -> BaCO3↓ + 2 NaCl"),
    ("p14", "осаждение", [R("CuSO4", .05), R("Na2S", .05)], W, "CuS", "CuSO4 + Na2S -> CuS↓ + Na2SO4"),
    ("p15", "осаждение", [R("ZnSO4", .05), R("Na2S", .05)], W, "ZnS", "ZnSO4 + Na2S -> ZnS↓ + Na2SO4"),
    ("p16", "осаждение", [R("Pb(NO3)2", .05), R("Na2S", .05)], W, "PbS", "Pb(NO3)2 + Na2S -> PbS↓ + 2 NaNO3"),
    ("p17", "осаждение", [R("AgNO3", .05), R("K2CrO4", .025)], W, "Ag2CrO4", "2 AgNO3 + K2CrO4 -> Ag2CrO4↓ + 2 KNO3"),
    ("p18", "осаждение", [R("Ba(NO3)2", .05), R("K2CrO4", .05)], W, "BaCrO4", "Ba(NO3)2 + K2CrO4 -> BaCrO4↓ + 2 KNO3"),
    ("p19", "осаждение", [R("AlCl3", .05), R("NaOH", .15)], W, "Al(OH)3", "AlCl3 + 3 NaOH -> Al(OH)3↓ + 3 NaCl"),
    ("p20", "осаждение", [R("NiSO4", .05), R("NaOH", .1)], W, "Ni(OH)2", "NiSO4 + 2 NaOH -> Ni(OH)2↓ + Na2SO4"),
    # --- ОВР (20)
    ("r01", "ОВР", [R("Zn", .05, "s"), R("CuSO4", .05)], W, "Cu", "Zn + CuSO4 -> Cu↓ + ZnSO4"),
    ("r02", "ОВР", [R("Fe", .05, "s"), R("CuSO4", .05)], W, "Cu", "Fe + CuSO4 -> Cu↓ + FeSO4"),
    ("r03", "ОВР", [R("Cu", .025, "s"), R("AgNO3", .05)], W, "Ag", "Cu + 2 AgNO3 -> 2 Ag↓ + Cu(NO3)2"),
    ("r04", "ОВР", [R("Zn", .1, "s"), R("HCl", .2)], W, "ZnCl2", "Zn + 2 HCl -> ZnCl2 + H2↑"),
    ("r05", "ОВР", [R("Fe", .1, "s"), R("HCl", .2)], W, "FeCl2", "Fe + 2 HCl -> FeCl2 + H2↑"),
    ("r06", "ОВР", [R("Mg", .1, "s"), R("H2SO4", .1)], W, "MgSO4", "Mg + H2SO4 -> MgSO4 + H2↑"),
    ("r07", "ОВР", [R("Al", .1, "s"), R("HCl", .3)], W, "AlCl3", "2 Al + 6 HCl -> 2 AlCl3 + 3 H2↑"),
    ("r08", "ОВР", [R("Cl2", .05, "g"), R("KBr", .1)], W, "Br2", "Cl2 + 2 KBr -> 2 KCl + Br2"),
    ("r09", "ОВР", [R("Br2", .005, "l"), R("KI", .01)], W, "I2", "Br2 + 2 KI -> 2 KBr + I2↓"),
    ("r10", "ОВР", [R("Mg", .1, "s"), R("HCl", .2)], W, "MgCl2", "Mg + 2 HCl -> MgCl2 + H2↑"),
    ("r11", "ОВР", [R("FeCl3", .02), R("SnCl2", .01), R("HCl", .1)], W, "FeCl2", "2 FeCl3 + SnCl2 -> 2 FeCl2 + SnCl4"),
    ("r12", "ОВР", [R("KMnO4", .02), R("FeSO4", .1), R("H2SO4", .08)], W, "Fe2(SO4)3",
     "2 KMnO4 + 10 FeSO4 + 8 H2SO4 -> 5 Fe2(SO4)3 + 2 MnSO4 + K2SO4 + 8 H2O"),
    ("r13", "ОВР", [R("K2Cr2O7", .01), R("FeSO4", .06), R("H2SO4", .07)], W, "Fe2(SO4)3",
     "K2Cr2O7 + 6 FeSO4 + 7 H2SO4 -> 3 Fe2(SO4)3 + Cr2(SO4)3 + K2SO4 + 7 H2O"),
    ("r14", "ОВР", [R("Cu", .03, "s"), R("HNO3", .08)], W, "Cu(NO3)2", "3 Cu + 8 HNO3 -> 3 Cu(NO3)2 + 2 NO↑ + 4 H2O"),
    ("r15", "ОВР", [R("H2O2", .01), R("KI", .02), R("H2SO4", .01)], W, "I2", "H2O2 + 2 KI + H2SO4 -> I2↓ + K2SO4 + 2 H2O"),
    ("r16", "ОВР", [R("Na", .1, "s")], W, "NaOH", "2 Na + 2 H2O -> 2 NaOH + H2↑"),
    ("r17", "ОВР", [R("Ca", .01, "s")], W, "Ca(OH)2", "Ca + 2 H2O -> Ca(OH)2 + H2↑"),
    ("r18", "ОВР", [R("K", .1, "s")], W, "KOH", "2 K + 2 H2O -> 2 KOH + H2↑"),
    ("r19", "ОВР", [R("Zn", .05, "s"), R("Pb(NO3)2", .05)], W, "Pb", "Zn + Pb(NO3)2 -> Pb↓ + Zn(NO3)2"),
    ("r20", "ОВР", [R("Na2SO3", .05), R("KMnO4", .02), R("H2SO4", .03)], W, "Na2SO4",
     "5 Na2SO3 + 2 KMnO4 + 3 H2SO4 -> 5 Na2SO4 + 2 MnSO4 + K2SO4 + 3 H2O"),
    # --- комплексы (10)
    ("c01", "комплексы", [R("CuSO4", .01), R("NH3", .04)], W, "Cu(NH3)4SO4", "CuSO4 + 4 NH3 -> Cu(NH3)4SO4"),
    ("c02", "комплексы", [R("AgCl", .01, "s"), R("NH3", .1)], W, "Ag(NH3)2Cl", "AgCl + 2 NH3 -> Ag(NH3)2Cl"),
    ("c03", "комплексы", [R("Zn(OH)2", .01, "s"), R("NaOH", .1)], W, "Na2Zn(OH)4", "Zn(OH)2 + 2 NaOH -> Na2Zn(OH)4"),
    ("c04", "комплексы", [R("Al(OH)3", .01, "s"), R("NaOH", .1)], W, "NaAl(OH)4", "Al(OH)3 + NaOH -> NaAl(OH)4"),
    ("c05", "комплексы", [R("NiSO4", .01), R("NH3", .1)], W, "Ni(NH3)6SO4", "NiSO4 + 6 NH3 -> Ni(NH3)6SO4"),
    ("c06", "комплексы", [R("AgNO3", .01), R("NH3", .1)], W, "Ag(NH3)2NO3", "AgNO3 + 2 NH3 -> Ag(NH3)2NO3"),
    ("c07", "комплексы", [R("CuCl2", .01), R("NH3", .1)], W, "Cu(NH3)4Cl2", "CuCl2 + 4 NH3 -> Cu(NH3)4Cl2"),
    ("c08", "комплексы", [R("FeSO4", .01), R("KCN", .06)], W, "K4Fe(CN)6", "FeSO4 + 6 KCN -> K4Fe(CN)6 + K2SO4"),
    ("c09", "комплексы", [R("Zn(NO3)2", .01), R("NaOH", .1)], W, "Na2Zn(OH)4",
     "Zn(NO3)2 + 4 NaOH -> Na2Zn(OH)4 + 2 NaNO3"),
    ("c10", "комплексы", [R("FeCl3", .01), R("KSCN", .01)], W, "FeSCNCl2", "FeCl3 + KSCN -> FeSCNCl2 + KCl"),
    # --- разложение (12)
    ("d01", "разложение", [R("CaCO3", .01, "s")], {**DRY, "temperature_K": 1200}, "CaO", "CaCO3 -> CaO + CO2↑"),
    ("d02", "разложение", [R("KClO3", .02, "s")], {**DRY, "temperature_K": 700}, "KCl", "2 KClO3 -> 2 KCl + 3 O2↑"),
    ("d03", "разложение", [R("KNO3", .02, "s")], {**DRY, "temperature_K": 750, "atmosphere": {"mode": "open"}},
     "KNO2", "2 KNO3 -> 2 KNO2 + O2↑"),
    ("d04", "разложение", [R("HgO", .02, "s")], {**DRY, "temperature_K": 800}, "Hg", "2 HgO -> 2 Hg↑ + O2↑"),
    ("d05", "разложение", [R("Cu(OH)2", .01, "s")], {**DRY, "temperature_K": 500}, "CuO", "Cu(OH)2 -> CuO + H2O↑"),
    ("d06", "разложение", [R("NaHCO3", .02, "s")], {**DRY, "temperature_K": 450}, "Na2CO3",
     "2 NaHCO3 -> Na2CO3 + CO2↑ + H2O↑"),
    ("d07", "разложение", [R("MgCO3", .01, "s")], {**DRY, "temperature_K": 900}, "MgO", "MgCO3 -> MgO + CO2↑"),
    ("d08", "разложение", [R("Fe(OH)3", .02, "s")], {**DRY, "temperature_K": 600}, "Fe2O3", "2 Fe(OH)3 -> Fe2O3 + 3 H2O↑"),
    ("d09", "разложение", [R("Ag2O", .02, "s")], {**DRY, "temperature_K": 700}, "Ag", "2 Ag2O -> 4 Ag + O2↑"),
    ("d10", "разложение", [R("Pb(NO3)2", .02, "s")], {**DRY, "temperature_K": 800, "atmosphere": {"mode": "open"}},
     "PbO", "2 Pb(NO3)2 -> 2 PbO + 4 NO2↑ + O2↑"),
    ("d11", "разложение", [R("Al(OH)3", .02, "s")], {**DRY, "temperature_K": 800}, "Al2O3", "2 Al(OH)3 -> Al2O3 + 3 H2O↑"),
    ("d12", "разложение", [R("CaSO4·2H2O", .01, "s")], {**DRY, "temperature_K": 500}, "CaSO4",
     "CaSO4·2H2O -> CaSO4 + 2 H2O↑"),
    # --- электрохимия (8): электролиз водных растворов
    ("e01", "электрохимия", [R("CuCl2", .05)], {**W, "electrolysis": {"enabled": True, "voltage_V": 2.0}}, "Cu",
     "CuCl2 -> Cu↓ + Cl2↑"),
    ("e02", "электрохимия", [R("NaCl", .1)], {**W, "electrolysis": {"enabled": True, "voltage_V": 4.0}}, "NaOH",
     "2 NaCl + 2 H2O -> 2 NaOH + H2↑ + Cl2↑"),
    ("e03", "электрохимия", [R("CuSO4", .05)], {**W, "electrolysis": {"enabled": True, "voltage_V": 2.0}}, "Cu",
     "2 CuSO4 + 2 H2O -> 2 Cu↓ + O2↑ + 2 H2SO4"),
    ("e04", "электрохимия", [R("Na2SO4", .1)], {**W, "electrolysis": {"enabled": True, "voltage_V": 3.0}}, "H2",
     "2 H2O -> 2 H2↑ + O2↑"),
    ("e05", "электрохимия", [R("KI", .1)], {**W, "electrolysis": {"enabled": True, "voltage_V": 2.0}}, "KOH",
     "2 KI + 2 H2O -> 2 KOH + H2↑ + I2↓"),
    ("e06", "электрохимия", [R("AgNO3", .05)], {**W, "electrolysis": {"enabled": True, "voltage_V": 2.0}}, "Ag",
     "4 AgNO3 + 2 H2O -> 4 Ag↓ + O2↑ + 4 HNO3"),
    ("e07", "электрохимия", [R("NaOH", .1)], {**W, "electrolysis": {"enabled": True, "voltage_V": 3.0}}, "H2",
     "2 H2O -> 2 H2↑ + O2↑"),
    ("e08", "электрохимия", [R("HCl", .1)], {**W, "electrolysis": {"enabled": True, "voltage_V": 2.0}}, "H2",
     "2 HCl -> H2↑ + Cl2↑"),
    # --- газовые реакции (15)
    ("g01", "газовые", [R("H2", .02, "g"), R("O2", .01, "g")], {**DRY, "temperature_K": 900}, "H2O", "2 H2 + O2 -> 2 H2O↑"),
    ("g02", "газовые", [R("NH3", .01, "g"), R("HCl", .01, "g")], DRY, "NH4Cl", "NH3 + HCl -> NH4Cl"),
    ("g03", "газовые", [R("NO", .02, "g"), R("O2", .01, "g")], DRY, "NO2", "2 NO + O2 -> 2 NO2↑"),
    ("g04", "газовые", [R("CH4", .01, "g"), R("O2", .02, "g")], {**DRY, "temperature_K": 900}, "CO2",
     "CH4 + 2 O2 -> CO2↑ + 2 H2O↑"),
    ("g05", "газовые", [R("CO", .02, "g"), R("O2", .01, "g")], {**DRY, "temperature_K": 900}, "CO2", "2 CO + O2 -> 2 CO2↑"),
    ("g06", "газовые", [R("H2", .01, "g"), R("Cl2", .01, "g")],
     {**DRY, "method": {"type": "photochemical", "wavelength_nm": 450}}, "HCl", "H2 + Cl2 -> 2 HCl↑"),
    ("g07", "газовые", [R("H2", .01, "g"), R("Br2", .01, "g")],
     {**DRY, "method": {"type": "photochemical", "wavelength_nm": 500}}, "HBr", "H2 + Br2 -> 2 HBr↑"),
    ("g08", "газовые", [R("Na2CO3", .1), R("HCl", .2)], W, "CO2", "Na2CO3 + 2 HCl -> 2 NaCl + CO2↑ + H2O"),
    ("g09", "газовые", [R("CaCO3", .1, "s"), R("HCl", .2)], W, "CO2", "CaCO3 + 2 HCl -> CaCl2 + CO2↑ + H2O"),
    ("g10", "газовые", [R("NH4Cl", .1), R("NaOH", .1)], W, "NH3", "NH4Cl + NaOH -> NH3 + NaCl + H2O"),
    ("g11", "газовые", [R("FeS", .3, "s"), R("HCl", .6)], W, "H2S", "FeS + 2 HCl -> FeCl2 + H2S↑"),
    ("g12", "газовые", [R("Na", .02, "s"), R("Cl2", .01, "g")], DRY, "NaCl", "2 Na + Cl2 -> 2 NaCl"),
    ("g13", "газовые", [R("NaHCO3", .1), R("HCl", .1)], W, "CO2", "NaHCO3 + HCl -> NaCl + CO2↑ + H2O"),
    ("g14", "газовые", [R("K2CO3", .1), R("H2SO4", .1)], W, "CO2", "K2CO3 + H2SO4 -> K2SO4 + CO2↑ + H2O"),
    ("g15", "газовые", [R("Fe", .02, "s"), R("S", .02, "s")], {**DRY, "temperature_K": 800}, "FeS", "Fe + S -> FeS"),
]


# Где учебник не выделяет один главный продукт, принимаются оба (соль и H2 у металла с кислотой и т. п.).
# Равновесные формы: 2 NO + O2 при 298 K и ~0,5 бар дают в основном N2O4 (Kp(2NO2 = N2O4) = 6,7 бар^-1).
ACCEPT_MAIN = {
    "r04": ["H2"], "r05": ["H2"], "r06": ["H2"], "r07": ["H2"], "r10": ["H2"], "r08": ["KCl"], "r09": ["KBr"],
    "r14": ["NO"], "r16": ["H2"], "r17": ["H2"], "r18": ["H2"],
    "d02": ["O2"], "d06": ["CO2"], "d09": ["O2"],
    "e02": ["H2", "Cl2"], "e05": ["H2", "I2"], "g03": ["N2O4"],
    "g08": ["NaCl"], "g09": ["CaCl2"], "g10": ["NaCl"], "g11": ["FeCl2"], "g13": ["NaCl"], "g14": ["K2SO4"],
}
ACCEPT_EQUATIONS = {"g03": ["2 NO + O2 -> N2O4↑"]}


def main():
    out = []
    for rid, cat, reag, cond, main_p, eq in POOL:
        out.append({"id": rid, "category": cat, "reagents": reag, "conditions": cond,
                    "expected_main": main_p, "accept_main": ACCEPT_MAIN.get(rid, []),
                    "expected_equation": eq, "accept_equations": ACCEPT_EQUATIONS.get(rid, [])})
    assert len(out) == 100 and len({r["id"] for r in out}) == 100
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT}: {len(out)} реакций")


if __name__ == "__main__":
    main()
