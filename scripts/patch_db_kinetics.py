import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # 1. Добавляем j0 в redox_pairs (базовая плотность тока обмена)
    try:
        cursor.execute("ALTER TABLE redox_pairs ADD COLUMN exchange_current_A_m2 REAL DEFAULT 1e-2")
    except sqlite3.OperationalError:
        pass

    # 2. Создаем таблицу для материалов электродов (чтобы можно было менять j0 в зависимости от металла)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS electrode_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material TEXT,
            reaction_key TEXT,
            j0_A_m2 REAL,
            alpha_a REAL DEFAULT 0.5,
            alpha_c REAL DEFAULT 0.5,
            UNIQUE(material, reaction_key)
        )
    """)

    # Заполняем базовыми данными (Pt для водорода/кислорода, C для хлора)
    materials_data = [
        # (material, reaction_key (ox_formula), j0, alpha_a, alpha_c)
        ("Pt", "H+", 1e-3, 0.5, 0.5),   # Водород на платине идет легко
        ("Pt", "O2", 1e-6, 0.5, 0.5),   # Кислород на платине идет тяжело (высокое перенапряжение)
        ("C", "Cl2", 1e-2, 0.5, 0.5),   # Хлор на графите идет хорошо
        ("Cu", "Cu+2", 1e-1, 0.5, 0.5), # Медь на меди
    ]

    for row in materials_data:
        try:
            cursor.execute("""
                INSERT INTO electrode_materials (material, reaction_key, j0_A_m2, alpha_a, alpha_c)
                VALUES (?, ?, ?, ?, ?)
            """, row)
        except sqlite3.IntegrityError:
            pass

    con.commit()
    con.close()
    print("✅ База данных обновлена: добавлены параметры кинетики.")

if __name__ == "__main__":
    main()