"""Скрипт миграции crc.db до версии Core v2.2 (электрохимия, кинетика, SIT)."""
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

    print("Создание новых таблиц...")
    
    # 1. Электрохимические пары (для расчета Нернста и электролиза)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS redox_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ox_formula TEXT, ox_phase TEXT,
            red_formula TEXT, red_phase TEXT,
            n_electrons INTEGER,
            e0_volts REAL,
            source TEXT
        )
    """)

    # 2. Кинетические барьеры (энергии активации)
    # Используем простые текстовые ключи для реакций (например, "S2O3-2+O2->SO4-2")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kinetic_barriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reaction_key TEXT UNIQUE,
            ea_kj_mol REAL,
            source TEXT
        )
    """)

    # 3. Параметры SIT (взаимодействие ионов)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sit_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ion1 TEXT,
            ion2 TEXT,
            epsilon REAL,
            source TEXT,
            UNIQUE(ion1, ion2)
        )
    """)

    print("Заполнение базовыми данными...")

    # --- Данные для redox_pairs ---
    # (ox_formula, ox_phase, red_formula, red_phase, n, e0, source)
    redox_data = [
        ("Fe+3", "aq", "Fe+2", "aq", 1, 0.771, "CRC"),
        ("MnO4-", "aq", "Mn+2", "aq", 5, 1.51, "CRC"),
        ("MnO4-", "aq", "MnO2", "s", 3, 1.69, "CRC"),
        ("S2O8-2", "aq", "SO4-2", "aq", 2, 2.01, "CRC"),
        ("S4O6-2", "aq", "S2O3-2", "aq", 2, 0.080, "CRC"),
        ("I2", "s", "I-", "aq", 2, 0.535, "CRC"),
        ("Cl2", "g", "Cl-", "aq", 2, 1.36, "CRC"),
        ("O2", "g", "H2O", "l", 4, 1.229, "CRC"), # Кислородный электрод (pH=0)
        ("H+", "aq", "H2", "g", 2, 0.000, "IUPAC"), # Водородный электрод
    ]
    
    for row in redox_data:
        try:
            cursor.execute("""
                INSERT INTO redox_pairs (ox_formula, ox_phase, red_formula, red_phase, n_electrons, e0_volts, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass # Уже существует

    # --- Данные для kinetic_barriers ---
    # (reaction_key, ea_kj_mol, source)
    kinetic_data = [
        # Окисление тиосульфата йодом идет быстро
        ("S2O3-2 + I2 -> S4O6-2 + I-", 40.0, "NBS"),
        # Окисление тиосульфата до сульфата идет крайне медленно без катализатора
        ("S2O3-2 + O2 -> SO4-2", 150.0, "Estimate"),
        # Разложение пероксида водорода (катализатор MnO2 снижает барьер)
        ("H2O2 -> H2O + O2", 75.0, "Estimate"),
    ]

    for row in kinetic_data:
        try:
            cursor.execute("""
                INSERT INTO kinetic_barriers (reaction_key, ea_kj_mol, source)
                VALUES (?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass

    # --- Данные для sit_parameters ---
    # (ion1, ion2, epsilon, source)
    sit_data = [
        ("H+", "Cl-", 0.12, "NEA"),
        ("Na+", "Cl-", 0.03, "NEA"),
        ("K+", "Cl-", 0.02, "NEA"),
        ("Na+", "OH-", 0.09, "NEA"),
    ]

    for row in sit_data:
        try:
            cursor.execute("""
                INSERT INTO sit_parameters (ion1, ion2, epsilon, source)
                VALUES (?, ?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass

    con.commit()
    con.close()
    print("✅ База данных успешно обновлена до Core v2.2!")

if __name__ == "__main__":
    main()