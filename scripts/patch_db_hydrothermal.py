"""Данные для гидротермального синтеза (W-07).

1. Al(OH)3(s): в базе только dGf из Ksp (-1134,69, CRC-Ksp), без dHf и S, поэтому G(T) = G(298) и
   Al(OH)3 + SiO2 -> каолинит при 473 K не шла. dGf(298) не меняется (растворимость при 298 K та же),
   добавлен dSf гиббсита: (dHf - dGf)/T0 по Robie & Hemingway 1995 (-1293,1 и -1154,9 кДж/моль)
   = -463,5 Дж/(моль K); dHf = dGf + T0·dSf. S и Cp - гиббсит (68,4 и 91,7). По памяти, не сверено.
2. Кинетическое правило aluminosilicate_lowT: алюмосиликаты (глины, цеолиты) при низкой температуре
   не кристаллизуются за время опыта - каолинит из гиббсита и кварца синтезируют гидротермально при
   150-250 °C. T_ref = 423 K, Ea по Эйрингу (t1/2 = 1 ч при T_ref) = 134,97 кДж/моль.
Идемпотентно. Запуск: python scripts/patch_db_hydrothermal.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
GIBBSITE_DSF = (-1293.1 - (-1154.9)) / T0 * 1000.0  # Дж/(моль K)
RULE = {
    "id": "aluminosilicate_lowT", "priority": 21, "kind": "formation", "ea_kj_mol": 134.97, "T_ref": 423,
    "title": "Алюмосиликаты не кристаллизуются при низкой температуре",
    "why": "Каолинит, цеолиты и другие алюмосиликаты из оксидов и гидроксидов при T < 420 K за часы не образуются "
           "(геологические времена); лабораторный синтез - гидротермальный, 150-250 °C.",
    "conditions": {}, "effect": {"forbid_new_class": "aluminosilicate"},
}
SOURCE = "W-07; Ea по Эйрингу (t1/2 = 1 ч при T_ref)"


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    row = cur.execute("SELECT id, dGf FROM species WHERE formula = 'Al(OH)3' AND phase = 's'").fetchone()
    if row:
        dGf = row[1]
        dHf = round(dGf + T0 * GIBBSITE_DSF / 1000.0, 2)
        cur.execute("UPDATE species SET dHf = ?, S = 68.4, Cp = 91.7, dSf = ?, note = ? WHERE id = ?",
                    (dHf, GIBBSITE_DSF, "dGf из Ksp; dSf, S, Cp - гиббсит (Robie & Hemingway 1995), W-07", row[0]))
        print(f"Al(OH)3: dHf = {dHf}, dSf = {GIBBSITE_DSF:.1f}")
    r = RULE
    vals = (r["ea_kj_mol"], SOURCE, r["kind"], r["priority"], r["title"], r["why"],
            json.dumps(r["conditions"], ensure_ascii=False), json.dumps(r["effect"], ensure_ascii=False), r["T_ref"])
    if cur.execute("SELECT 1 FROM kinetic_barriers WHERE reaction_key = ?", (r["id"],)).fetchone():
        cur.execute("UPDATE kinetic_barriers SET ea_kj_mol=?, source=?, kind=?, priority=?, title=?, why=?, "
                    "conditions=?, effect=?, T_ref=? WHERE reaction_key=?", (*vals, r["id"]))
    else:
        cur.execute("INSERT INTO kinetic_barriers (ea_kj_mol, source, kind, priority, title, why, conditions, "
                    "effect, T_ref, reaction_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*vals, r["id"]))
    print(f"kinetic_barriers: {r['id']}")
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
