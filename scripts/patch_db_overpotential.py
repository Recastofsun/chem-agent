import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # Добавляем колонку перенапряжения
    try:
        cursor.execute("ALTER TABLE redox_pairs ADD COLUMN overpotential_V REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    # Задаем перенапряжение для ключевых реакций (Вольты)
    overpotentials = {
        ("O2", "H2O"): 0.50,   # Кислород на Pt
        ("Cl2", "Cl-"): 0.10,  # Хлор на графите/Pt
        ("H+", "H2"): 0.00,    # Водород на Pt
        ("S2O8-2", "SO4-2"): 0.80 # Персульфат (очень высокое)
    }

    for (ox, red), eta in overpotentials.items():
        cursor.execute("""
            UPDATE redox_pairs 
            SET overpotential_V = ? 
            WHERE ox_formula = ? AND red_formula = ?
        """, (eta, ox, red))

    con.commit()
    con.close()
    print("✅ База данных обновлена: добавлено перенапряжение.")

if __name__ == "__main__":
    main()