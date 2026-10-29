"""Тетраэтоксисилан Si(OC2H5)4(l) для золь-гель метода (W-09).

ΔfH°(l, 298,15 K) = -1408,0 ± 2,1 кДж/моль - van der Vis, Cordfunke, J. Chem. Thermodyn. 25 (1993),
https://www.sciencedirect.com/science/article/abs/pii/S0021961483711183
S°(l) = 533,1 Дж/(моль K), Cp(l, 298 K) = 364,4 Дж/(моль K) - van der Vis et al., J. Chem. Thermodyn. 24
(1992) 1103, по NIST WebBook (C78104).
ΔfS = S - ΣS(элементов): Si 18,81; C(графит) 5,74; H2 130,68; O2 205,15 (CODATA).
ΔfG = ΔfH - T0·ΔfS = -1035,7 кДж/моль. Контроль: TEOS + 2 H2O(l) -> SiO2 + 4 C2H5OH(l), ΔG = -46 кДж/моль.
Идемпотентно. Запуск: python scripts/patch_db_teos.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
DHF, S, CP = -1408.0, 533.1, 364.4
S_ELEM = 18.81 + 8 * 5.74 + 10 * 130.68 + 2 * 205.15  # Si + 8 C + 10 H2 + 2 O2
DSF = S - S_ELEM                                        # Дж/(моль K)
DGF = round(DHF - T0 * DSF / 1000.0, 2)


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cols = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"
    row = ("Si(OC2H5)4", "C8H20O4Si", json.dumps({"Si": 1, "O": 4, "C": 8, "H": 20}), 0, "l",
           "Tetraethoxysilane (TEOS)", "тетраэтоксисилан (TEOS)", DGF, DHF, S, CP, DSF,
           "vanderVis-Cordfunke-1993", 2.5, "dHf - калориметрия растворения; S, Cp - NIST WebBook")
    ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 'l'", (row[0],)).fetchone()
    if ex:
        cur.execute(f"UPDATE species SET ({cols}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
    else:
        cur.execute(f"INSERT INTO species ({cols}) VALUES ({', '.join('?' * 15)})", row)
    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    print(f"Si(OC2H5)4(l): dGf = {DGF}, dSf = {DSF:.1f}")


if __name__ == "__main__":
    main()
