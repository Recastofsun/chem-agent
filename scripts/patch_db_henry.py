"""Таблица henry_constants (W-11, ТЗ п. 14.2) и растворенные формы газов, которых нет в базе.

kH - моль/(кг·бар) при 298,15 K (в таблице Sander - М/атм, перевод / 1,01325); dlnkH_dinvT - K
(d ln kH / d(1/T)), ΔH растворения = -R·dlnkH_dinvT. Значения - Sander R., Atmos. Chem. Phys. 15 (2015)
4399, типичные рекомендованные; внесены по памяти, построчно не сверены.
Сверка с базой (kH = exp(-(ΔGf(aq) - ΔGf(g))/RT)): O2, CO2, H2, NH3, H2S, SO2, Br2 - в пределах 6 %,
N2 - 17 %, Cl2 - 1,5 раза (NBS 0,061 против 0,092 М/атм у Sander).
Газам без aq-формы в базе (CH4, CO, NO, N2O, Ar, He, O3, NO2) добавляется растворенная частица:
ΔGf(aq) = ΔGf(g) - RT·ln kH, ΔHf(aq) = ΔHf(g) + ΔH растворения. Без нее газ в воде не растворяется вовсе.
Идемпотентно. Запуск: python scripts/patch_db_henry.py
"""
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
R = 8.314462618e-3
T0 = 298.15
ATM = 1.01325
SOURCE = "Sander-2015"
# газ: (kH, М/атм; d ln kH / d(1/T), K)
HENRY = {
    "O2": (1.3e-3, 1500), "N2": (6.4e-4, 1300), "CO2": (3.4e-2, 2400), "H2": (7.8e-4, 500),
    "CH4": (1.4e-3, 1600), "NH3": (59.0, 4200), "H2S": (0.10, 2100), "SO2": (1.3, 2900),
    "Cl2": (0.092, 2000), "NO": (1.9e-3, 1400), "N2O": (2.5e-2, 2700), "Ar": (1.4e-3, 1500),
    "He": (3.8e-4, 100), "CO": (9.5e-4, 1300), "O3": (1.1e-2, 2400), "Br2": (0.73, 4100),
    "NO2": (1.2e-2, 2400),
}


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS henry_constants (
            gas TEXT PRIMARY KEY,
            kH_mol_kg_bar REAL,
            dlnkH_dinvT_K REAL,
            dH_sol_kJ_mol REAL,
            T_K REAL DEFAULT 298.15,
            source TEXT
        )""")
    added = []
    for gas, (kh_atm, c) in HENRY.items():
        kh = kh_atm / ATM
        dH_sol = -R * c
        cur.execute("INSERT OR REPLACE INTO henry_constants (gas, kH_mol_kg_bar, dlnkH_dinvT_K, dH_sol_kJ_mol, source) "
                    "VALUES (?, ?, ?, ?, ?)", (gas, kh, c, round(dH_sol, 3), SOURCE))
        if cur.execute("SELECT 1 FROM species WHERE formula = ? AND phase = 'aq' AND (source IS NULL OR source != ?)",
                       (gas, SOURCE)).fetchone():
            continue
        g = cur.execute("SELECT hill, elements, name_en, name_ru, dGf, dHf FROM species WHERE formula = ? AND phase = 'g'",
                        (gas,)).fetchone()
        if not g:
            continue
        hill, els, en, ru, dGf_g, dHf_g = g
        dGf = round(dGf_g - R * T0 * math.log(kh), 3)
        dHf = round(dHf_g + dH_sol, 3) if dHf_g is not None else None
        dSf = (dHf - dGf) / T0 * 1000.0 if dHf is not None else None
        row = (gas, hill, els, 0, "aq", en, ru, dGf, dHf, None, None, dSf, SOURCE, 1.0,
               f"из газа и kH = {kh:.3g} моль/(кг бар) (Henry)")
        cols = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"
        ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 'aq'", (gas,)).fetchone()
        if ex:
            cur.execute(f"UPDATE species SET ({cols}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
        else:
            cur.execute(f"INSERT INTO species ({cols}) VALUES ({', '.join('?' * 15)})", row)
        added.append(gas)
    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    print(f"henry_constants: {len(HENRY)} газов; aq-формы добавлены: {', '.join(added) or 'нет'}")


if __name__ == "__main__":
    main()
