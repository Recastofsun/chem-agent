"""Добавление HS- (гидросульфид) в crc.db (W-26)."""
import json
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "chem_agent" / "data" / "crc.db"

# Табличное значение из CRC Handbook
DG_HS = -17.7

def main():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Проверяем, есть ли HS-
    existing = cur.execute(
        "SELECT id, dGf FROM species WHERE formula = 'HS-' AND phase = 'aq'"
    ).fetchone()
    
    if existing:
        print(f"⚠️  HS- уже есть в CRC (id={existing[0]}, dGf={existing[1]}), пропускаем")
        con.close()
        return
    
    # Добавляем HS-
    cur.execute("""
        INSERT INTO species 
        (formula, hill, phase, elements, charge, dGf, source, sigma, name_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "HS-",
        "HS-",
        "aq",
        json.dumps({"H": 1, "S": 1}),
        -1,
        DG_HS,
        "CRC_Handbook",
        1.0,
        "Hydrosulfide ion"
    ))
    
    con.commit()
    
    # Проверяем
    result = cur.execute(
        "SELECT formula, phase, dGf, source FROM species WHERE formula = 'HS-' AND phase = 'aq'"
    ).fetchone()
    
    if result:
        print(f"✅ Добавлен HS-(aq): dGf = {result[2]} кДж/моль, source = {result[3]}")
    else:
        print("❌ Ошибка: HS- не добавился!")
    
    con.close()

if __name__ == "__main__":
    main()