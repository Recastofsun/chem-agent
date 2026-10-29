"""Силикаты для методов синтеза (W-06...W-08): волластонит, ларнит, каолинит.

Без них тестовые реакции ТЗ невозможны: CaCO3 + SiO2 -> CaSiO3 + CO2 (W-06, W-08),
Al(OH)3 + SiO2 -> каолинит (W-07). В базе были только SiO2, Na2SiO3, Mg2SiO4 и др.

Значения - Robie & Hemingway (1995), USGS Bull. 2131, 298,15 K. Внесены по памяти, с первоисточником
построчно не сверены (sigma 2 кДж/моль). Контроль: CaO + SiO2 -> CaSiO3, ΔG = -90 кДж/моль
(литература около -89). Идемпотентно. Запуск: python scripts/patch_db_silicates.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
SOURCE = "Robie-Hemingway-1995"
NOTE = "Robie & Hemingway 1995 (USGS Bull. 2131); по памяти, не сверено построчно"

# formula, hill, elements, name_en, name_ru, dGf, dHf (кДж/моль), S, Cp (Дж/(моль K))
SILICATES = [
    ("CaSiO3", "CaO3Si", {"Ca": 1, "Si": 1, "O": 3}, "Calcium metasilicate (wollastonite)",
     "метасиликат кальция (волластонит)", -1549.66, -1634.94, 81.92, 85.27),
    ("Ca2SiO4", "Ca2O4Si", {"Ca": 2, "Si": 1, "O": 4}, "Calcium orthosilicate (larnite)",
     "ортосиликат кальция (ларнит)", -2193.2, -2307.5, 127.6, 128.7),
    ("Al2Si2O5(OH)4", "Al2H4O9Si2", {"Al": 2, "Si": 2, "O": 9, "H": 4}, "Kaolinite",
     "каолинит", -3799.4, -4119.6, 200.9, 246.1),
]


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cols = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"
    for f, hill, els, en, ru, g, h, s, cp in SILICATES:
        dSf = (h - g) / T0 * 1000.0
        row = (f, hill, json.dumps(els), 0, "s", en, ru, g, h, s, cp, dSf, SOURCE, 2.0, NOTE)
        ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 's'", (f,)).fetchone()
        if ex:
            cur.execute(f"UPDATE species SET ({cols}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
        else:
            cur.execute(f"INSERT INTO species ({cols}) VALUES ({', '.join('?' * 15)})", row)
        print(f"{f}: dGf = {g}")
    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
