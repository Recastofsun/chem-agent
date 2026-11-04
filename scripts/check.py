"""Добавление параметров Pitzer для Mg+2/Cl- в crc.db."""
import sqlite3
from pathlib import Path

DB_PATH = Path('chem_agent/data/crc.db')

# Параметры из Pitzer 1973, HMW 1984
PITZER_PARAMS = {
    ("Mg+2", "Cl-"): {
        "beta0": 0.3524,
        "beta1": 1.6815,
        "beta2": 0.0,
        "C_phi": 0.00519,
        "source": "Pitzer1973_HMW1984"
    }
}

def add_pitzer_params():
    if not DB_PATH.exists():
        print(f"❌ База не найдена: {DB_PATH}")
        return
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Проверяем существование таблицы
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pitzer_parameters'")
    if not cur.fetchone():
        print("❌ Таблица pitzer_parameters не существует")
        con.close()
        return
    
    added = 0
    for (ion1, ion2), params in PITZER_PARAMS.items():
        # Проверяем, есть ли уже параметры
        cur.execute(
            "SELECT COUNT(*) FROM pitzer_parameters WHERE ion1 = ? AND ion2 = ?",
            (ion1, ion2)
        )
        if cur.fetchone()[0] > 0:
            print(f"  {ion1}/{ion2}: уже существуют, обновляем")
            cur.execute(
                """UPDATE pitzer_parameters 
                   SET beta0 = ?, beta1 = ?, beta2 = ?, C_phi = ?, source = ?
                   WHERE ion1 = ? AND ion2 = ?""",
                (params["beta0"], params["beta1"], params["beta2"], 
                 params["C_phi"], params["source"], ion1, ion2)
            )
        else:
            cur.execute(
                """INSERT INTO pitzer_parameters 
                   (ion1, ion2, beta0, beta1, beta2, C_phi, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ion1, ion2, params["beta0"], params["beta1"], 
                 params["beta2"], params["C_phi"], params["source"])
            )
        added += 1
        print(f"✓ {ion1}/{ion2}: β0={params['beta0']}, β1={params['beta1']}, Cφ={params['C_phi']}")
    
    con.commit()
    con.close()
    print(f"\n✅ Добавлено/обновлено {added} пар параметров Pitzer")

if __name__ == "__main__":
    add_pitzer_params()