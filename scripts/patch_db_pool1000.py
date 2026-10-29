"""Исправления данных и правил, найденные пулом 1000 (W-16). Идемпотентно.

1. Запись 'TiO' (id 1176) - на деле Ti3O5 (имя "Titanium(III,IV) oxide", ΔfG -2317,4 кДж/моль - значения CRC
   для Ti3O5): формула при импорте схлопнулась. Запись переименована в Ti3O5, добавлен настоящий TiO(тв) по CRC:
   ΔfH -542,7, ΔfG -513,3 кДж/моль, S 34,8, Cp 40,0 Дж/(моль K). Раньше Ti + O2 давал "TiO" вместо TiO2.
2. SnCl2(aq) = -429,0 кДж/моль (NBS) на 140 кДж стабильнее Sn2+ + 2 Cl- (-289,6): соответствует lg β2 ~ 24,
   у хлоридных комплексов Sn(II) lg β2 ~ 2. Из-за этого Fe, Ni, Co, Cd не восстанавливали олово из SnCl2.
   Оценка: ΔfG = ΔfG(Sn2+) + 2 ΔfG(Cl-) - RT ln10 · 2,0 = -301,0 кДж/моль (оценка, sigma 6).
3. Mn(OH)2(тв): нет ΔfH и S, разложение при нагреве не считалось. NBS-1982 (аморфный): ΔfH -695,4,
   S 99,2 (ΔfG -615,0 согласуется с записью из Ksp -614,9).
4. PbF2(тв): ΔfG CRC дает pKsp 6,15, таблица Ksp CRC - 3,3e-8 (pKsp 7,48); осадок PbF2 почти не выпадал.
   ΔfG пересчитан из Ksp по ионам базы.
5. Правила mn_neutral_stop / mn_alkaline_stop: группа "others" содержала Mn(0), металлический марганец
   не окислялся в растворе вовсе (Mn + CuSO4 - нет реакции). Mn(0) перенесен в группу Mn(II/III).
6. Правило sulfate_only_inert: sulfate_inert выключается при любом сильном окислителе (так сульфид и сульфит
   могут окислиться до сульфата), а Cu2+ и Fe3+ считаются сильными окислителями - Sn + CuSO4 давал Cu2S.
   Новое правило: если вся сера реагентов - S(VI), сульфат в растворе не восстанавливается при любых
   окислителях (кроме горячей концентрированной H2SO4). Ea и T_ref - как у sulfate_inert.
Запуск: python scripts/patch_db_pool1000.py
"""
import json
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)
COLS = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"


def g(cur, formula, phase="aq"):
    return cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = ?", (formula, phase)).fetchone()[0]


def main():
    if not DB_PATH.exists():
        print(f"База не найдена: {DB_PATH}")
        return
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    # 1. Ti3O5 / TiO
    cur.execute("UPDATE species SET formula = 'Ti3O5', hill = 'O5Ti3', elements = ?, name_ru = 'оксид титана(III,IV)' "
                "WHERE name_en = 'Titanium(III,IV) oxide'", (json.dumps({"O": 5, "Ti": 3}),))
    s_elem = 30.7 + 0.5 * 205.15
    tio = ("TiO", "OTi", json.dumps({"O": 1, "Ti": 1}), 0, "s", "Titanium(II) oxide", "оксид титана(II)",
           -513.3, -542.7, 34.8, 40.0, 34.8 - s_elem, "CRC", 1.0, "W-16: настоящий TiO (запись 1176 - Ti3O5)")
    ex = cur.execute("SELECT id FROM species WHERE formula = 'TiO' AND phase = 's'").fetchone()
    if ex:
        cur.execute(f"UPDATE species SET ({COLS}) = ({', '.join('?' * 15)}) WHERE id = ?", (*tio, ex[0]))
    else:
        cur.execute(f"INSERT INTO species ({COLS}) VALUES ({', '.join('?' * 15)})", tio)
    # 2. SnCl2(aq)
    dg = round(g(cur, "Sn+2") + 2 * g(cur, "Cl-") - RT_LN10 * 2.0, 2)
    cur.execute("UPDATE species SET dGf = ?, dHf = NULL, S = NULL, dSf = NULL, source = 'estimate', sigma = 6.0, "
                "note = 'W-16: из Sn2+ + 2 Cl- и lg β2 = 2,0 (NBS -429,0 несовместимо с ионами базы)' "
                "WHERE formula = 'SnCl2' AND phase = 'aq'", (dg,))
    # 3. Mn(OH)2
    dsf = 99.2 - (32.01 + 205.15 + 130.68)
    cur.execute("UPDATE species SET dHf = -695.4, S = 99.2, dSf = ?, note = ? WHERE formula = 'Mn(OH)2' AND phase = 's'",
                (dsf, "из Ksp = 2.06e-13 (25 C); dHf, S - NBS-1982 (аморфный), W-16"))
    # 4. PbF2
    dg_pbf2 = round(g(cur, "Pb+2") + 2 * g(cur, "F-") - RT_LN10 * 7.48, 2)
    cur.execute("UPDATE species SET dGf = ?, dSf = (dHf - ?) / 0.29815, source = 'CRC-Ksp', "
                "note = 'W-16: dGf из Ksp = 3.3e-8 (таблица Ksp CRC) по ионам базы' "
                "WHERE formula = 'PbF2' AND phase = 's'", (dg_pbf2, dg_pbf2))
    # 5. правила марганца
    for key, groups in (("mn_neutral_stop", [[7, 6, 4], [0, 2, 3], ["others"]]),
                        ("mn_alkaline_stop", [[7, 6], [4], [0, 2, 3], ["others"]])):
        eff = json.loads(cur.execute("SELECT effect FROM kinetic_barriers WHERE reaction_key = ?", (key,)).fetchone()[0])
        eff["decouple"]["groups"] = groups
        cur.execute("UPDATE kinetic_barriers SET effect = ? WHERE reaction_key = ?",
                    (json.dumps(eff, ensure_ascii=False), key))
    # 6. sulfate_only_inert
    rule = ("sulfate_only_inert", 127.39, "W-16; Ea как у sulfate_inert (t1/2 = 1 ч при 400 K)", "redox", 7,
            "Сульфат не восстанавливается (сера только S(VI))",
            "SO4(2-) кинетически инертен; если другой серы в реагентах нет, окислитель в системе этого не меняет.",
            json.dumps({"aqueous": True, "no_conc_sulfuric_hot": True, "sulfur_only_vi": True}),
            json.dumps({"decouple": {"element": "S", "groups": [[6], ["others"]]}}), 400.0)
    if cur.execute("SELECT 1 FROM kinetic_barriers WHERE reaction_key = ?", (rule[0],)).fetchone():
        cur.execute("UPDATE kinetic_barriers SET ea_kj_mol=?, source=?, kind=?, priority=?, title=?, why=?, "
                    "conditions=?, effect=?, T_ref=? WHERE reaction_key=?", (*rule[1:], rule[0]))
    else:
        cur.execute("INSERT INTO kinetic_barriers (reaction_key, ea_kj_mol, source, kind, priority, title, why, "
                    "conditions, effect, T_ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rule)
    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    print(f"Ti3O5/TiO, SnCl2(aq) = {dg}, Mn(OH)2, PbF2 = {dg_pbf2}, правила Mn, sulfate_only_inert")


if __name__ == "__main__":
    main()
