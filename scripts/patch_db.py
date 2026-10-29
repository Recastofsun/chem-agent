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

    # Данные для внедрения: (formula, phase, elements_json, charge, dGf, dHf, S, Cp, dSf, source, sigma, name_en, name_ru, note)
    new_species = [
        # Тетратионат натрия (для реакции Na2S2O3 + I2)
        ("Na2S4O6", "aq", json.dumps({"Na": 2, "S": 4, "O": 6}), 0, -1024.0, -1064.0, 300.0, None, None, "NBS-1982", 10.0, "sodium tetrathionate", "тетратионат натрия", "оценка"),
        # Ион тетратионата
        ("S4O6-2", "aq", json.dumps({"S": 4, "O": 6}), -2, -1110.0, -1150.0, 250.0, None, None, "NBS-1982", 10.0, "tetrathionate ion", "тетратионат-ион", "оценка")
    ]

    count = 0
    for sp in new_species:
        try:
            cursor.execute("""
                INSERT INTO species (formula, phase, elements, charge, dGf, dHf, S, Cp, dSf, source, sigma, name_en, name_ru, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sp)
            count += 1
            print(f"✅ Добавлено: {sp[0]} ({sp[1]})")
        except sqlite3.IntegrityError:
            print(f"ℹ️ Уже существует: {sp[0]} ({sp[1]})")
        except Exception as e:
            print(f"❌ Ошибка при добавлении {sp[0]}: {e}")

    con.commit()
    con.close()
    print(f"\nГотово. Добавлено {count} новых частиц.")

if __name__ == "__main__":
    main()