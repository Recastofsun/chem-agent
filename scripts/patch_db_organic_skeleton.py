"""Правило organic_skeleton_lowT в kinetic_barriers (W-04, исправление CO2).

Пока цианидное правило срабатывало в любой водной реакции, оно попутно запрещало C2O4-2, CO, CO2,
и распад органики не был виден. После исправления CH3COOH + NaOH дает CH4 и оксалат (5 %):
диспропорционирование ацетата термодинамически выгодно, но кинетически невозможно.
Правило: при органическом реагенте ниже ~600 K не образуются новые неорганические частицы углерода
не в степени +4 (CH4, CO, оксалаты, карбиды, цианиды). Ea - как у no_new_carbon_lowT (t1/2 = 1 ч при 600 K).
Идемпотентно. Запуск: python scripts/patch_db_organic_skeleton.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
SOURCE = "W-04; Ea по Эйрингу (t1/2 = 1 ч при T_ref), как no_new_carbon_lowT"
RULE = {
    "id": "organic_skeleton_lowT",
    "priority": 19,
    "kind": "formation",
    "ea_kj_mol": 193.12,
    "T_ref": 600,
    "title": "Углеродный скелет органики не распадается при низкой температуре",
    "why": "Разрыв связей C-C и C-H органического реагента (ацетат -> CH4 + оксалат, CO) при T < 600 K "
           "без катализатора кинетически заторможен; идут только кислотно-основные превращения.",
    "conditions": {"organic_reagent": True},
    "effect": {"forbid_new_class": "carbon_fragment"},
}


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    r = RULE
    vals = (r["ea_kj_mol"], SOURCE, r["kind"], r["priority"], r["title"], r["why"],
            json.dumps(r["conditions"], ensure_ascii=False), json.dumps(r["effect"], ensure_ascii=False), r["T_ref"])
    if cur.execute("SELECT 1 FROM kinetic_barriers WHERE reaction_key = ?", (r["id"],)).fetchone():
        cur.execute("UPDATE kinetic_barriers SET ea_kj_mol=?, source=?, kind=?, priority=?, title=?, why=?, "
                    "conditions=?, effect=?, T_ref=? WHERE reaction_key=?", (*vals, r["id"]))
    else:
        cur.execute("INSERT INTO kinetic_barriers (ea_kj_mol, source, kind, priority, title, why, conditions, "
                    "effect, T_ref, reaction_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*vals, r["id"]))
    con.commit()
    con.close()
    print(f"kinetic_barriers: {r['id']}")


if __name__ == "__main__":
    main()
