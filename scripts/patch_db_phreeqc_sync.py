"""Синхронизация базы данных с эталоном PHREEQC (v2.5.2)."""
import math
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "chem_agent" / "data" / "crc.db"
PHREEQC_PATH = ROOT / "data" / "phreeqc.dat"

T0 = 298.15
RT_LN10 = 8.314462618e-3 * T0 * math.log(10)  # ~5.708 кДж/моль

def get_g(cur, formula, phase="aq"):
    row = cur.execute("SELECT dGf FROM species WHERE formula = ? AND phase = ?", (formula, phase)).fetchone()
    return row[0] if row else None

def parse_phreeqc():
    """Вытаскиваем уравнения и log_k для нужных нам веществ."""
    if not PHREEQC_PATH.exists():
        print(f"Ошибка: Файл {PHREEQC_PATH} не найден!")
        return []

    text = PHREEQC_PATH.read_text(encoding="utf-8", errors="ignore")
    
    # Нас интересуют только эти блоки
    blocks = []
    current_block = []
    
    # Очень простой парсер: ищем строки с "=" и "log_k" или "log_K"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            current_block.append(line)
        elif line.startswith("log_k") or line.startswith("log_K"):
            if current_block:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        log_k = float(parts[1])
                        current_block.append(log_k)
                        blocks.append(current_block)
                    except ValueError:
                        pass
            current_block = []
        elif not line:
            current_block = []
            
    return blocks

def main():
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    # Карта названий PHREEQC -> наши формулы
    aliases = {
        "Ca+2": "Ca+2", "Ba+2": "Ba+2", "Mg+2": "Mg+2", "Na+": "Na+", "K+": "K+",
        "CO3-2": "CO3-2", "HCO3-": "HCO3-", "SO4-2": "SO4-2", "Cl-": "Cl-",
        "H+": "H+", "OH-": "OH-", "H2O": "H2O"
    }

    blocks = parse_phreeqc()
    updated_count = 0
    
    for block in blocks:
        eq = block[0].replace(" ", "")
        log_k = block[1]
        
        # 1. Комплексы (например, Ca+2 + CO3-2 = CaCO3)
        if "=" in eq and "+" in eq:
            left, right = eq.split("=")
            if right in ("CaCO3", "CaHCO3+", "BaSO4", "CaSO4"):  # Нас интересуют эти комплексы
                products = right
                reactants = left.split("+")
                
                # Считаем dG комплекса
                dg_reactants = 0
                valid = True
                for r in reactants:
                    # Очистка от коэффициентов (например, 2H2O)
                    coeff = 1
                    match = re.match(r'^(\d+)(.+)$', r)
                    if match:
                        coeff = int(match.group(1))
                        r = match.group(2)
                    
                    if r in aliases:
                        g = get_g(cur, aliases[r], "aq")
                        if g is not None:
                            dg_reactants += g * coeff
                        else:
                            valid = False
                            break
                    else:
                        valid = False
                        break
                        
                if valid:
                    dg_prod = dg_reactants - RT_LN10 * log_k
                    print(f"Комплекс {products}: dGf = {dg_prod:.2f} (log K = {log_k})")
                    # Обновляем или вставляем в базу (упрощенно)
                    cur.execute("UPDATE species SET dGf = ?, source = 'phreeqc.dat' WHERE formula = ? AND phase = 'aq'", (round(dg_prod, 2), products))
                    if cur.rowcount == 0:
                        # Тут должен быть INSERT, но для простоты мы обновляем только существующие
                        pass
                    updated_count += 1

        # 2. Минералы (например, Calcite + H+ = Ca+2 + HCO3-)
        # В блоке PHASES первая строка - название минерала, вторая - реакция, третья - log_k
        # Наш простой парсер сюда не достает, поэтому допишем жестко для двух минералов:
    
    # Жесткая перезапись для Кальцита и Барита по данным из phreeqc.dat
    # Calcite: CaCO3 = Ca+2 + CO3-2, log_k = -8.48
    g_ca = get_g(cur, "Ca+2", "aq")
    g_co3 = get_g(cur, "CO3-2", "aq")
    if g_ca and g_co3:
        dg_calcite = g_ca + g_co3 - RT_LN10 * (-8.48)
        cur.execute("UPDATE species SET dGf = ?, source = 'phreeqc.dat' WHERE formula = 'CaCO3' AND phase = 's'", (round(dg_calcite, 2),))
        print(f"Минерал CaCO3(s): dGf = {dg_calcite:.2f}")

    # Barite: BaSO4 = Ba+2 + SO4-2, log_k = -9.97
    g_ba = get_g(cur, "Ba+2", "aq")
    g_so4 = get_g(cur, "SO4-2", "aq")
    if g_ba and g_so4:
        dg_barite = g_ba + g_so4 - RT_LN10 * (-9.97)
        cur.execute("UPDATE species SET dGf = ?, source = 'phreeqc.dat' WHERE formula = 'BaSO4' AND phase = 's'", (round(dg_barite, 2),))
        print(f"Минерал BaSO4(s): dGf = {dg_barite:.2f}")

    con.commit()
    con.close()
    print(f"Обновлено записей: {updated_count}")

if __name__ == "__main__":
    main()