"""Миграция crc.db для v2.5 (W-14): таблица pitzer_parameters + гипс CaSO4·2H2O(s).

Параметры Pitzer - Harvie, Moller, Weare (1984), 25 C (те же, что в pitzer.dat PHREEQC).
Гипс: dGf подогнан под log Ksp = -4.581 (pitzer.dat), что с полной моделью Pitzer
воспроизводит экспериментальную растворимость 0.0152 моль/кг при 25 C.
NBS-1982 дает dGf = -1797.28, но в паре с ионами CRC это log Ksp = -4.38 и растворимость 0.022.
dHf, S, Cp - NBS-1982.

Скрипт идемпотентен: повторный запуск обновляет параметры, гипс не дублирует.
"""
import json
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"

# ion1 (катион или первый ион пары), ion2, beta0, beta1, beta2, C_phi, theta, psi, source
PITZER = [
    ("Na+", "Cl-", 0.0765, 0.2664, 0.0, 0.00127, 0.0, 0.0, "HMW1984"),
    ("Ca+2", "SO4-2", 0.2000, 3.1973, -54.24, 0.0, 0.0, 0.0, "HMW1984"),
    ("Ca+2", "Cl-", 0.3159, 1.614, 0.0, -0.00034, 0.0, 0.0, "HMW1984"),
    ("Mg+2", "SO4-2", 0.2210, 3.343, -37.23, 0.025, 0.0, 0.0, "HMW1984"),
    ("Na+", "SO4-2", 0.0196, 1.113, 0.0, 0.0045, 0.0, 0.0, "HMW1984"),
    ("K+", "Cl-", 0.0483, 0.2122, 0.0, -0.00084, 0.0, 0.0, "HMW1984"),
    ("H+", "Cl-", 0.1775, 0.2945, 0.0, 0.00080, 0.0, 0.0, "HMW1984"),
]

LOG_KSP_GYPSUM = -4.581
T0 = 298.15
R = 8.314462618e-3  # кДж/(моль K)


def gypsum_row(con) -> tuple:
    g = dict(con.execute(
        "SELECT formula, dGf FROM species WHERE (formula, phase) IN "
        "(VALUES ('Ca+2','aq'), ('SO4-2','aq'), ('H2O','l'))").fetchall())
    # CaSO4·2H2O(s) = Ca+2 + SO4-2 + 2 H2O(l);  dG_r = -RT ln K
    dG_r = -R * T0 * math.log(10) * LOG_KSP_GYPSUM
    dGf = round(g["Ca+2"] + g["SO4-2"] + 2 * g["H2O"] - dG_r, 2)
    dHf = -2022.63
    dSf = (dHf - dGf) / T0 * 1000.0
    return ("CaSO4·2H2O", "CaH4O6S", json.dumps({"Ca": 1, "H": 4, "O": 6, "S": 1}), 0, "s",
            "Calcium sulfate dihydrate (gypsum)", "гипс (сульфат кальция дигидрат)",
            dGf, dHf, 194.1, 186.02, dSf, "NBS-1982+fit",
            0.5, f"dGf подогнан под log Ksp = {LOG_KSP_GYPSUM} (pitzer.dat, HMW1984)")


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pitzer_parameters (
            ion1 TEXT,
            ion2 TEXT,
            beta0 REAL,
            beta1 REAL,
            beta2 REAL,
            C_phi REAL,
            theta REAL DEFAULT 0.0,
            psi REAL DEFAULT 0.0,
            source TEXT,
            PRIMARY KEY (ion1, ion2)
        )""")
    cur.executemany("INSERT OR REPLACE INTO pitzer_parameters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", PITZER)
    print(f"pitzer_parameters: {len(PITZER)} пар")

    row = gypsum_row(con)
    exists = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 's'", (row[0],)).fetchone()
    cols = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"
    if exists:
        cur.execute(f"UPDATE species SET ({cols}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, exists[0]))
        print(f"гипс обновлен: dGf = {row[7]} кДж/моль")
    else:
        cur.execute(f"INSERT INTO species ({cols}) VALUES ({', '.join('?' * 15)})", row)
        print(f"гипс добавлен: dGf = {row[7]} кДж/моль")

    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
