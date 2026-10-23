import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # Добавляем колонки, если их нет
    try:
        cursor.execute("ALTER TABLE redox_pairs ADD COLUMN ox_coeff REAL DEFAULT 1.0")
        cursor.execute("ALTER TABLE redox_pairs ADD COLUMN red_coeff REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass  # Уже добавлены

    # Обновляем коэффициенты для пары O2 / H2O
    # O2 + 4H+ + 4e- -> 2H2O (на 1 моль O2 приходится 4e-, на 2 моля H2O - 4e-, т.е. на 1 моль H2O - 2e-)
    cursor.execute("""
        UPDATE redox_pairs 
        SET ox_coeff = 1.0, red_coeff = 2.0 
        WHERE ox_formula = 'O2' AND red_formula = 'H2O'
    """)
    
    # Для остальных пар (Fe3+/Fe2+, MnO4-/Mn2+ и т.д.) коэффициенты 1:1
    cursor.execute("""
        UPDATE redox_pairs 
        SET ox_coeff = 1.0, red_coeff = 1.0 
        WHERE (ox_formula != 'O2' OR red_formula != 'H2O')
    """)

    con.commit()
    con.close()
    print("✅ Таблица redox_pairs обновлена коэффициентами.")

if __name__ == "__main__":
    main()