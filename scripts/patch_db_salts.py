"""Добавление недостающих осадков (оксалатов и фосфатов) на основе Ksp (W-16 v2.5.1)."""
import json
import math
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"
T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)
COLS = "formula, hill, elements, charge, phase, name_en, name_ru, dGf, dHf, S, Cp, dSf, source, sigma, note"

def get_g(cur, formula, phase="aq"):
    row = cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = ?", (formula, phase)).fetchone()
    if not row:
        raise ValueError(f"В базе нет иона {formula}({phase})")
    return row[0]

def main():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    # Данные: формула, Hill, элементы, Ksp (в виде -log10), англ.название, рус.название, ионы для расчета
    # dGf = sum(dGf_ions) - RT*ln(10)*(-pKsp)
    
    salts = [
        # Оксалаты
        ("Ag2C2O4", "C2Ag2O4", {"Ag": 2, "C": 2, "O": 4}, 11.0, "Silver oxalate", "оксалат серебра", [("Ag+", 2), ("C2O4-2", 1)]),
        ("BaC2O4",  "C2BaO4",  {"Ba": 1, "C": 2, "O": 4}, 6.96, "Barium oxalate", "оксалат бария", [("Ba+2", 1), ("C2O4-2", 1)]),
        ("CaC2O4",  "C2CaO4",  {"Ca": 1, "C": 2, "O": 4}, 8.59, "Calcium oxalate", "оксалат кальция", [("Ca+2", 1), ("C2O4-2", 1)]),
        ("SrC2O4",  "C2O4Sr",  {"Sr": 1, "C": 2, "O": 4}, 7.25, "Strontium oxalate", "оксалат стронция", [("Sr+2", 1), ("C2O4-2", 1)]),
        ("MgC2O4",  "C2MgO4",  {"Mg": 1, "C": 2, "O": 4}, 4.07, "Magnesium oxalate", "оксалат магния", [("Mg+2", 1), ("C2O4-2", 1)]),
        ("PbC2O4",  "C2O4Pb",  {"Pb": 1, "C": 2, "O": 4}, 9.77, "Lead(II) oxalate", "оксалат свинца", [("Pb+2", 1), ("C2O4-2", 1)]),
        # Фосфаты
        ("Sr3(PO4)2", "O8P2Sr3", {"Sr": 3, "P": 2, "O": 8}, 27.4, "Strontium phosphate", "фосфат стронция", [("Sr+2", 3), ("PO4-3", 2)]),
        ("Cu3(PO4)2", "Cu3O8P2", {"Cu": 3, "P": 2, "O": 8}, 36.85, "Copper(II) phosphate", "фосфат меди(II)", [("Cu+2", 3), ("PO4-3", 2)]),
        ("Zn3(PO4)2", "O8P2Zn3", {"Zn": 3, "P": 2, "O": 8}, 32.04, "Zinc phosphate", "фосфат цинка", [("Zn+2", 3), ("PO4-3", 2)]),
        ("FePO4", "FeO4P", {"Fe": 1, "P": 1, "O": 4}, 21.89, "Iron(III) phosphate", "фосфат железа(III)", [("Fe+3", 1), ("PO4-3", 1)]),
        ("Fe3(PO4)2", "Fe3O8P2", {"Fe": 3, "P": 2, "O": 8}, 36.0, "Iron(II) phosphate", "фосфат железа(II)", [("Fe+2", 3), ("PO4-3", 2)]),
        ("Ni3(PO4)2", "Ni3O8P2", {"Ni": 3, "P": 2, "O": 8}, 31.3, "Nickel(II) phosphate", "фосфат никеля(II)", [("Ni+2", 3), ("PO4-3", 2)]),
        ("Co3(PO4)2", "Co3O8P2", {"Co": 3, "P": 2, "O": 8}, 34.7, "Cobalt(II) phosphate", "фосфат кобальта(II)", [("Co+2", 3), ("PO4-3", 2)]),
        ("Mn3(PO4)2", "Mn3O8P2", {"Mn": 3, "P": 2, "O": 8}, 36.0, "Manganese(II) phosphate", "фосфат марганца(II)", [("Mn+2", 3), ("PO4-3", 2)]),
        ("Cd3(PO4)2", "Cd3O8P2", {"Cd": 3, "P": 2, "O": 8}, 32.6, "Cadmium phosphate", "фосфат кадмия", [("Cd+2", 3), ("PO4-3", 2)])
    ]

    added = 0
    for formula, hill, elements, pksp, name_en, name_ru, ion_parts in salts:
        try:
            g_ions = sum(get_g(cur, ion) * coeff for ion, coeff in ion_parts)
        except ValueError as e:
            print(f"Пропущен {formula}: {e}")
            continue
        
        # dGf = sum(dGf_ions) - RT*ln(10)*(-pKsp)
        dg = round(g_ions - RT_LN10 * (-pksp), 2)
        
        row = (
            formula, hill, json.dumps(elements), 0, "s", name_en, name_ru,
            dg, None, None, None, None, "CRC-Ksp", 2.0, f"W-16: dGf из Ksp = 10^-{pksp} по ионам базы"
        )
        
        ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 's'", (formula,)).fetchone()
        if ex:
            cur.execute(f"UPDATE species SET ({COLS}) = ({', '.join('?' * 15)}) WHERE id = ?", (*row, ex[0]))
        else:
            cur.execute(f"INSERT INTO species ({COLS}) VALUES ({', '.join('?' * 15)})", row)
            added += 1

    # Обновляем счетчик в meta
    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    print(f"Добавлено/обновлено веществ: {added}. Всего в базе: {n}")

if __name__ == "__main__":
    main()