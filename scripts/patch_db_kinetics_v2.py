import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
    con = sqlite3.connect(str(db_path))
    cursor = con.cursor()

    for col in ("overpotential_V", "exchange_current_A_m2"):
        try:
            cursor.execute(f"ALTER TABLE redox_pairs ADD COLUMN {col} REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass

    kinetics_data = [
        # (ox, red, e0, n, overpotential_V, exchange_current_A_m2)
        ("O2", "H2O", 1.229, 4, 0.50, 1e-6),
        ("Cl2", "Cl-", 1.360, 2, 0.10, 1e-2),
        ("H+", "H2", 0.000, 2, 0.00, 1e-3),
    ]

    for ox, red, e0, n, eta, j0 in kinetics_data:
        cursor.execute("""
            UPDATE redox_pairs 
            SET e0_volts = ?, n_electrons = ?, overpotential_V = ?, exchange_current_A_m2 = ?
            WHERE ox_formula = ? AND red_formula = ?
        """, (e0, n, eta, j0, ox, red))

    con.commit()
    con.close()
    print("✅ База данных обновлена.")

if __name__ == "__main__":
    main()