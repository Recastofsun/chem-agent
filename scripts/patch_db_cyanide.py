"""Правило cyanide_no_hydrolysis (W-15).

В W-04 правило cyanide_complexes_stable сужено до цианидных комплексов. После этого свободный цианид
(FeSO4 + 6 KCN) "распадался" на NH3 + оксалат + CH4: гидролиз и диспропорционирование CN-
термодинамически выгодны, но связь C≡N при комнатной температуре за часы не рвется (гидролиз цианида -
сутки и кипячение с кислотой или щелочью). Правило запрещает продукты разрыва C≡N при любом цианидном
реагенте (KCN, HCN, K4[Fe(CN)6]); HCN и CN- не запрещены - протонирование и комплексообразование идут.
Ea - как у cyanide_complexes_stable (t1/2 = 1 ч при 400 K). Идемпотентно.
Запуск: python scripts/patch_db_cyanide.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
SOURCE = "W-15; Ea по Эйрингу (t1/2 = 1 ч при T_ref), как cyanide_complexes_stable"
RULE = {
    "id": "cyanide_no_hydrolysis", "priority": 34, "kind": "ligand", "ea_kj_mol": 127.39, "T_ref": 400,
    "title": "Цианид не гидролизуется при низкой температуре",
    "why": "Разрыв связи C≡N (CN- -> NH3 + формиат, оксалат, CO2) при T < 400 K без катализатора идет сутками; "
           "в растворе цианид остается CN-/HCN или в комплексе.",
    "conditions": {"aqueous": True, "reagent_class": "cyanide"},
    "effect": {"forbid_new": ["NH3", "NH4+", "C2O4-2", "HC2O4-", "H2C2O4", "CO2", "CO", "CH4", "HCOO-", "HCOOH",
                              "HCO3-", "CO3-2", "OCN-", "HOCN"]},
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
