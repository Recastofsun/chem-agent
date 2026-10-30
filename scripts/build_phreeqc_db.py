"""Создание независимой базы данных phreeqc.db на базе crc.db с синхронизацией из phreeqc.dat (W-26)."""
import json
import math
import re
import shutil
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chem_agent.parser.formula import parse_formula

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "chem_agent" / "data" / "phreeqc.db"
CRC_PATH = ROOT / "chem_agent" / "data" / "crc.db"
DAT_PATH = ROOT / "data" / "phreeqc.dat"

T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)

def get_g_crc(cur, formula):
    row = cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = 'aq'", (formula,)).fetchone()
    return row[0] if row else None

def parse_reaction_side(side_str):
    parts = side_str.split(" + ")
    res = []
    for p in parts:
        p = p.strip()
        if not p: continue
        m = re.match(r'^(\d+)([A-Za-z].*)$', p)
        if m:
            res.append((m.group(2), int(m.group(1))))
        else:
            res.append((p, 1))
    return res

def main():
    if not DAT_PATH.exists():
        print(f"Ошибка: Файл {DAT_PATH} не найден!")
        return

    # 1. Копируем crc.db в phreeqc.db
    if DB_PATH.exists():
        DB_PATH.unlink()
    shutil.copy(str(CRC_PATH), str(DB_PATH))
    print(f"База phreeqc.db создана как копия crc.db.")

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    lines = DAT_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    
    BLOCKS = {"SOLUTION_MASTER_SPECIES", "SOLUTION_SPECIES", "PHASES"}
    
    current_block = None
    g_map = {} 
    updated = 0
    inserted = 0
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line or line.startswith("#"):
            i += 1
            continue
            
        if line in BLOCKS:
            current_block = line
            i += 1
            continue
        if line == "END":
            current_block = None
            i += 1
            continue
            
        if current_block == "SOLUTION_SPECIES":
            if "=" in line:
                eq = line.split("#")[0].strip()
                if "=" not in eq:
                    i += 1
                    continue
                left_str, right_str = eq.split("=", 1)
                
                log_k = None
                j = i + 1
                while j < len(lines) and j < i + 10:
                    parts = lines[j].split()
                    if len(parts) >= 2 and parts[0].lower() in ("log_k", "-log_k"):
                        try:
                            log_k = float(parts[1])
                            break
                        except ValueError:
                            pass
                    j += 1
                
                if log_k is not None:
                    left = parse_reaction_side(left_str)
                    right = parse_reaction_side(right_str)
                    
                    if len(right) == 1:
                        product = right[0][0]
                        dg_reactants = 0
                        valid = True
                        for f, c in left:
                            g = g_map.get(f) or get_g_crc(cur, f)
                            if g is None:
                                valid = False
                                break
                            dg_reactants += g * c
                            
                        if valid:
                            dg_prod = dg_reactants - RT_LN10 * log_k
                            g_map[product] = dg_prod
                            
                            # Парсим формулу, чтобы получить элементы и заряд!
                            try:
                                comp = parse_formula(product)
                                elements = json.dumps(comp.as_dict)
                                charge = comp.charge
                            except Exception:
                                elements = "{}"
                                charge = 0
                                
                            ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 'aq'", (product,)).fetchone()
                            if ex:
                                cur.execute("UPDATE species SET dGf = ?, source = 'phreeqc.dat', note = 'synced' WHERE id = ?", (round(dg_prod, 2), ex[0]))
                                updated += 1
                            else:
                                cur.execute("""INSERT INTO species (formula, hill, phase, elements, charge, dGf, source, sigma, name_en) 
                                               VALUES (?, ?, 'aq', ?, ?, ?, 'phreeqc.dat', 1.0, ?)""",
                                            (product, product, elements, charge, round(dg_prod, 2), product))
                                inserted += 1

        elif current_block == "PHASES":
            if "=" in line:
                eq = line.split("#")[0].strip()
                if "=" not in eq:
                    i += 1
                    continue
                left_str, right_str = eq.split("=", 1)
                
                phase_name = None
                k = i - 1
                while k >= 0:
                    prev_line = lines[k].strip()
                    if prev_line and not prev_line.startswith("#"):
                        phase_name = prev_line.split()[0]
                        break
                    k -= 1
                
                if not phase_name:
                    i += 1
                    continue
                
                log_k = None
                j = i + 1
                while j < len(lines) and j < i + 15:
                    parts = lines[j].split()
                    if len(parts) >= 2 and parts[0].lower() in ("log_k", "-log_k"):
                        try:
                            log_k = float(parts[1])
                            break
                        except ValueError:
                            pass
                    j += 1
                    
                if log_k is not None:
                    left = parse_reaction_side(left_str)
                    right = parse_reaction_side(right_str)
                    
                    dg_left = 0
                    dg_right = 0
                    valid = True
                    for f, c in left:
                        g = g_map.get(f) or get_g_crc(cur, f)
                        if g is None: valid = False; break
                        dg_left += g * c
                    for f, c in right:
                        g = g_map.get(f) or get_g_crc(cur, f)
                        if g is None: valid = False; break
                        dg_right += g * c
                        
                    if valid:
                        dg_mineral = dg_right - dg_left - RT_LN10 * log_k
                        
                        if phase_name == "Calcite": target_formula = "CaCO3"
                        elif phase_name == "Barite": target_formula = "BaSO4"
                        elif phase_name == "Gypsum": target_formula = "CaSO4·2H2O"
                        else: target_formula = phase_name
                            
                        try:
                            comp = parse_formula(target_formula)
                            elements = json.dumps(comp.as_dict)
                            charge = comp.charge
                        except Exception:
                            elements = "{}"
                            charge = 0

                        ex = cur.execute("SELECT id FROM species WHERE formula = ? AND phase = 's'", (target_formula,)).fetchone()
                        if ex:
                            cur.execute("UPDATE species SET dGf = ?, source = 'phreeqc.dat', note = 'synced' WHERE id = ?", (round(dg_mineral, 2), ex[0]))
                            updated += 1
                        else:
                            cur.execute("""INSERT INTO species (formula, hill, phase, elements, charge, dGf, source, sigma, name_en) 
                                           VALUES (?, ?, 's', ?, ?, ?, 'phreeqc.dat', 1.0, ?)""",
                                        (target_formula, target_formula, elements, charge, round(dg_mineral, 2), phase_name))
                            inserted += 1
        i += 1

    n = cur.execute("SELECT count(*) FROM species").fetchone()[0]
    cur.execute("UPDATE meta SET value = ? WHERE key = 'species_count'", (str(n),))
    con.commit()
    con.close()
    
    print(f"Успешно обновлено (синхронизировано): {updated}")
    print(f"Успешно добавлено новых: {inserted}")
    print(f"Всего в базе: {n}")

if __name__ == "__main__":
    main()