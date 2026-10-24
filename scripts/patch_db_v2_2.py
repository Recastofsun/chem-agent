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

    print("1. Создание и обновление таблиц...")
    
    # 1. Электрохимические пары
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
    # Добавляем колонки коэффициентов, если их нет
    for col in ("ox_coeff", "red_coeff"):
        try:
            cursor.execute(f"ALTER TABLE redox_pairs ADD COLUMN {col} REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass

    # 2. Кинетические барьеры
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kinetic_barriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reaction_key TEXT UNIQUE,
            ea_kj_mol REAL,
            source TEXT
        )
    """)

    # 3. Параметры SIT
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

    print("2. Добавление новых веществ в species...")
    # Добавляем персульфат-ион в основную таблицу
    new_species = [
        # Тетратионат натрия
        ("Na2S4O6", "aq", json.dumps({"Na": 2, "S": 4, "O": 6}), 0, -1024.0, -1064.0, 300.0, None, None, "NBS-1982", 10.0, "sodium tetrathionate", "тетратионат натрия", "оценка"),
        # Ион тетратионата
        ("S4O6-2", "aq", json.dumps({"S": 4, "O": 6}), -2, -1110.0, -1150.0, 250.0, None, None, "NBS-1982", 10.0, "tetrathionate ion", "тетратионат-ион", "оценка"),
        # Персульфат-ион (для электролиза сульфатов)
        ("S2O8-2", "aq", json.dumps({"S": 2, "O": 8}), -2, -1110.0, -1150.0, 250.0, None, None, "NBS-1982", 10.0, "persulfate ion", "персульфат-ион", "оценка")
    ]
    for sp in new_species:
        try:
            cursor.execute("""
                INSERT INTO species (formula, phase, elements, charge, dGf, dHf, S, Cp, dSf, source, sigma, name_en, name_ru, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sp)
        except sqlite3.IntegrityError:
            pass # Уже существует

    print("3. Заполнение базовыми данными...")

    # --- Данные для redox_pairs ---
    # (ox_formula, ox_phase, red_formula, red_phase, n, e0, source, ox_coeff, red_coeff)
    redox_data = [
        ("Fe+3", "aq", "Fe+2", "aq", 1, 0.771, "CRC", 1.0, 1.0),
        ("MnO4-", "aq", "Mn+2", "aq", 5, 1.51, "CRC", 1.0, 1.0),
        ("MnO4-", "aq", "MnO2", "s", 3, 1.69, "CRC", 1.0, 1.0),
        ("S2O8-2", "aq", "SO4-2", "aq", 2, 2.01, "CRC", 1.0, 2.0),
        ("S4O6-2", "aq", "S2O3-2", "aq", 2, 0.080, "CRC", 1.0, 2.0),
        ("I2", "s", "I-", "aq", 2, 0.535, "CRC", 1.0, 2.0),
        ("Cl2", "g", "Cl-", "aq", 2, 1.36, "CRC", 1.0, 2.0),
        ("O2", "g", "H2O", "l", 4, 1.229, "CRC", 1.0, 2.0), 
        ("H+", "aq", "H2", "g", 2, 0.000, "IUPAC", 2.0, 1.0), 
        ("Cu+2", "aq", "Cu", "s", 2, 0.34, "CRC", 1.0, 1.0),
    ]
    
    for row in redox_data:
        try:
            cursor.execute("""
                INSERT INTO redox_pairs (ox_formula, ox_phase, red_formula, red_phase, n_electrons, e0_volts, source, ox_coeff, red_coeff)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass

    # --- Данные для kinetic_barriers ---
    kinetic_data = [
        ("S2O3-2 + I2 -> S4O6-2 + I-", 40.0, "NBS"),
        ("S2O3-2 + O2 -> SO4-2", 150.0, "Estimate"),
        ("H2O2 -> H2O + O2", 75.0, "Estimate"),
    ]
    for row in kinetic_data:
        try:
            cursor.execute("INSERT INTO kinetic_barriers (reaction_key, ea_kj_mol, source) VALUES (?, ?, ?)", row)
        except sqlite3.IntegrityError:
            pass

    # --- Данные для sit_parameters ---
    sit_data = [
        ("H+", "Cl-", 0.12, "NEA"),
        ("Na+", "Cl-", 0.03, "NEA"),
        ("K+", "Cl-", 0.02, "NEA"),
        ("Na+", "OH-", 0.09, "NEA"),
    ]
    for row in sit_data:
        try:
            cursor.execute("INSERT INTO sit_parameters (ion1, ion2, epsilon, source) VALUES (?, ?, ?, ?)", row)
        except sqlite3.IntegrityError:
            pass

    con.commit()
    con.close()
    print("✅ База данных успешно обновлена до Core v2.2!")

if __name__ == "__main__":
    main()