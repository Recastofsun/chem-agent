# Скрипт для исправления dGf FeCl3 и проверки FeCl2
"""Исправление dGf для хлоридов железа."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"

CORRECTIONS = [
    # FeCl3(aq): пересчет из ионов Fe3+ + 3Cl-
    ("FeCl3", "aq", -398.3, "NBS_recalc", "Пересчет: Fe3+(-4.7) + 3Cl-(-131.2)"),
    
    # FeCl2(aq): пересчет из ионов Fe2+ + 2Cl-
    ("FeCl2", "aq", -341.3, "NBS_recalc", "Пересчет: Fe2+(-78.9) + 2Cl-(-131.2)"),
]

def fix_dGf():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    for formula, phase, new_dGf, source, note in CORRECTIONS:
        cur.execute(
            "UPDATE species SET dGf = ?, source = ?, note = ? WHERE formula = ? AND phase = ?",
            (new_dGf, source, note, formula, phase)
        )
        if cur.rowcount > 0:
            print(f"✓ {formula}({phase}): dGf обновлен на {new_dGf} кДж/моль")
        else:
            print(f"⚠️  {formula}({phase}) не найден")
    
    con.commit()
    con.close()

if __name__ == "__main__":
    fix_dGf()