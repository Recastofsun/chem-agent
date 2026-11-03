"""Добавление FeCl2(aq) в БД."""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"

def compute_hill_formula(elements: dict) -> str:
    if not elements: return ""
    c_count = elements.get("C", 0)
    h_count = elements.get("H", 0)
    others = {k: v for k, v in elements.items() if k not in ("C", "H")}
    result = []
    if "C" in elements: result.append(f"C{c_count if c_count != 1 else ''}")
    if "H" in elements: result.append(f"H{h_count if h_count != 1 else ''}")
    for el in sorted(others.keys()):
        count = others[el]
        result.append(f"{el}{count if count != 1 else ''}")
    return "".join(result)

SPECIES_TO_ADD = [
    ("FeCl2", "aq", {"Fe": 1, "Cl": 2}, 0, -341.30, "NBS_recalc", 
     "Хлорид железа(II), водный раствор (расчет из ионов: Fe2+ + 2Cl-)"),
]

def add_species():
    if not DB_PATH.exists():
        print(f"❌ База не найдена: {DB_PATH}")
        return
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    added = 0
    for formula, phase, elements, charge, dGf, source, note in SPECIES_TO_ADD:
        existing = cur.execute(
            "SELECT formula FROM species WHERE formula = ? AND phase = ?",
            (formula, phase)
        ).fetchone()
        
        if existing:
            print(f"✓ {formula}({phase}) уже есть")
            continue
        
        hill = compute_hill_formula(elements)
        elements_json = json.dumps(elements)
        
        cur.execute(
            "INSERT INTO species (formula, phase, elements, charge, dGf, source, note, hill, sigma, dHf, S, Cp, dSf, name_en, name_ru) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (formula, phase, elements_json, charge, dGf, source, note, hill, 
             1.0, None, None, None, None, "", None)
        )
        added += 1
        print(f"+ Добавлено: {formula}({phase}) dGf={dGf} кДж/моль")
    
    con.commit()
    con.close()
    print(f"\n✅ Добавлено {added} веществ.")

if __name__ == "__main__":
    add_species()