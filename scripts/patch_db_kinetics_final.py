import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # 1. Убедимся, что колонки есть
    for col in ("overpotential_V", "exchange_current_A_m2"):
        try:
            cursor.execute(f"ALTER TABLE redox_pairs ADD COLUMN {col} REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass

    # 2. Принудительно обновляем данные
    # O2 (кислород) - очень высокое перенапряжение, низкий ток обмена
    cursor.execute("UPDATE redox_pairs SET overpotential_V = 0.50, exchange_current_A_m2 = 1e-6 WHERE ox_formula = 'O2'")
    
    # Cl2 (хлор) - низкое перенапряжение, высокий ток обмена
    cursor.execute("UPDATE redox_pairs SET overpotential_V = 0.10, exchange_current_A_m2 = 1e-2 WHERE ox_formula = 'Cl2'")
    
    # H2 (водород) - нулевое перенапряжение, средний ток
    cursor.execute("UPDATE redox_pairs SET overpotential_V = 0.00, exchange_current_A_m2 = 1e-3 WHERE ox_formula = 'H+'")
    
    # Cu (медь) - нулевое перенапряжение, высокий ток
    cursor.execute("UPDATE redox_pairs SET overpotential_V = 0.00, exchange_current_A_m2 = 1e-1 WHERE ox_formula = 'Cu+2'")

    con.commit()

    # 3. ПРОВЕРКА: Выводим то, что реально лежит в базе
    print("=== ПРОВЕРКА БАЗЫ ДАННЫХ ===")
    cursor.execute("SELECT ox_formula, red_formula, overpotential_V, exchange_current_A_m2 FROM redox_pairs")
    for row in cursor.fetchall():
        if row[0] in ("O2", "Cl2", "H+", "Cu+2"):
            print(f"{row[0]}/{row[1]}: eta={row[2]:.2f}, j0={row[3]:.1e}")

    con.close()

if __name__ == "__main__":
    main()