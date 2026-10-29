"""Добавление гидрокарбонатных комплексов кальция (W-34)."""
import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "chem_agent" / "data" / "crc.db"
T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)
COLS = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"

def get_g(cur, formula, phase="aq"):
    return cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = ?", (formula, phase)).fetchone()[0]

def add_species(cur, formula, elements, charge, name_en, name_ru, ions, log_beta):
    # dGf = sum(dGf_ions) - RT*ln(10) * log_beta
    dg_ions = sum(get_g(cur, f) * c for f, c in ions)
    dg = round(dg_ions - RT_LN10 * log_beta, 2)
    
    # Hill formula
    from chem_agent.parser.formula import conventional_formula
    hill = conventional_formula(elements, charge)
    
    row = (formula, hill, json.dumps(elements), charge, "aq", name_en, name_ru,
           dg, None, None, None, None, "NIST", 2.0, f"W-34: lg beta = {log_beta}")
    
    ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 'aq'", (formula,)).fetchone()
    if ex:
        cur.execute(f"UPDATE species SET ({COLS}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
        print(f"{formula} обновлен")
    else:
        cur.execute(f"INSERT INTO species ({COLS}) VALUES ({', '.join('?' * 15)})", row)
        print(f"{formula} добавлен")

def main():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Ca2+ + HCO3- <=> CaHCO3+ (lg beta = 1.11)
    add_species(cur, "CaHCO3+", {"Ca": 1, "H": 1, "C": 1, "O": 3}, 1, 
                "Calcium bicarbonate", "гидрокарбонат кальция", 
                [("Ca+2", 1), ("HCO3-", 1)], 1.11)
                
    # Ca2+ + CO3-2 <=> CaCO3(aq) (lg beta = 3.22)
    add_species(cur, "CaCO3", {"Ca": 1, "C": 1, "O": 3}, 0, 
                "Calcium carbonate ion pair", "карбонат кальция (ионная пара)", 
                [("Ca+2", 1), ("CO3-2", 1)], 3.22)

    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    print(f"Всего в базе: {n}")

if __name__ == "__main__":
    main()