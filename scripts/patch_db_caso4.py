import sqlite3
import json
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    if not db_path.exists():
        print(f"❌ База не найдена: {db_path}")
        return

    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # Данные для добавления: CaSO4(aq)
    # dGf = -1302.4, dHf = -1453.2, S = 20.0
    sp = (
        "CaSO4", "aq", json.dumps({"Ca": 1, "S": 1, "O": 4}), 0, 
        -1302.4, -1453.2, 20.0, None, None, 
        "NBS-1982", 1.5, "calcium sulfate ion pair", "сульфат кальция (ионная пара)", 
        "ионная пара"
    )

    try:
        cursor.execute("""
            INSERT INTO species (formula, phase, elements, charge, dGf, dHf, S, Cp, dSf, source, sigma, name_en, name_ru, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sp)
        print("✅ Успешно добавлено: CaSO4 (aq)")
    except sqlite3.IntegrityError:
        print("ℹ️ Уже существует: CaSO4 (aq)")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    con.commit()
    con.close()

if __name__ == "__main__":
    main()