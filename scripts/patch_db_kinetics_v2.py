import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    # Жестко задаем j0 (ток обмена) и overpotential (перенапряжение)
    kinetics_data = [
        # (ox, red, e0, n, overpotential_V, exchange_current_A_m2)
        ("O2", "H2O", 1.229, 4, 0.50, 1e-6),   # Кислород: очень низкий ток обмена
        ("Cl2", "Cl-", 1.360, 2, 0.10, 1e-2),  # Хлор: высокий ток обмена
        ("H+", "H2", 0.000, 2, 0.00, 1e-3),    # Водород: средний ток
        ("Cu+2", "Cu", 0.340, 2, 0.00, 1e-1),  # Медь: очень высокий ток обмена
    ]

    for ox, red, e0, n, eta, j0 in kinetics_data:
        cursor.execute("""
            UPDATE redox_pairs 
            SET e0_volts = ?, n_electrons = ?, overpotential_V = ?, exchange_current_A_m2 = ?
            WHERE ox_formula = ? AND red_formula = ?
        """, (e0, n, eta, j0, ox, red))

    con.commit()
    con.close()
    print("✅ База данных обновлена: j0 и перенапряжение заданы.")

if __name__ == "__main__":
    main()