"""Добавление нейтральных ионных пар для точной валидации (W-34)."""
import json
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)
COLS = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"

def get_g(cur, formula, phase="aq"):
    return cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = ?", (formula, phase)).fetchone()[0]

def main():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # BaSO4(aq) - ионная пара. lg beta = 2.7 (из литературных данных)
    dg_baso4 = round(get_g(cur, "Ba+2") + get_g(cur, "SO4-2") - RT_LN10 * 2.7, 2)
    row = ("BaSO4", "BaO4S", json.dumps({"Ba": 1, "S": 1, "O": 4}), 0, "aq", 
           "Barium sulfate ion pair", "сульфат бария (ионная пара)", 
           dg_baso4, None, None, None, None, "Literature", 2.0, "W-34: lg beta = 2.7")
           
    ex = cur.execute("SELECT id FROM species WHERE formula = 'BaSO4' AND phase = 'aq'").fetchone()
    if ex:
        cur.execute(f"UPDATE species SET ({COLS}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
        print("BaSO4(aq) обновлен")
    else:
        cur.execute(f"INSERT INTO species ({COLS}) VALUES ({', '.join('?' * 15)})", row)
        print("BaSO4(aq) добавлен")

    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()

if __name__ == "__main__":
    main()