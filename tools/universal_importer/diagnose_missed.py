"""Диагностика пропущенных реакций при импорте (W-26)."""
import json
import math
import re
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from chem_agent.parser.formula import parse_formula

CRC_PATH = ROOT / "chem_agent" / "data" / "crc.db"
MANIFEST_PATH = ROOT / "tools" / "universal_importer" / "manifest.json"
RAW_JSON_PATH = ROOT / "tools" / "phreeqc_importer" / "phreeqc_raw.json"


def clean_formula_complex(formula: str) -> str:
    """Нормализует формулу водного комплекса БЕЗ раскрытия скобок."""
    if not formula:
        return formula
    
    formula = formula.replace("  ", " ").replace(": ", "·").replace(":", "·").strip()
    
    m_charge = re.search(r'([+-]{2,})$', formula)
    if m_charge:
        sign = m_charge.group(1)[0]
        count = len(m_charge.group(1))
        formula = formula[:m_charge.start()] + f"{sign}{count}"
    
    return formula


def clean_formula_mineral(formula: str) -> str:
    """Нормализует формулу минерала С раскрытием скобок."""
    if not formula:
        return formula
    
    formula = formula.replace("  ", " ").replace(": ", "·").replace(":", "·").strip()
    
    m_charge = re.search(r'([+-]{2,})$', formula)
    if m_charge:
        sign = m_charge.group(1)[0]
        count = len(m_charge.group(1))
        formula = formula[:m_charge.start()] + f"{sign}{count}"
    
    max_iterations = 10
    iteration = 0
    while "(" in formula and iteration < max_iterations:
        m = re.search(r'\(([^()]+)\)(\d*)', formula)
        if not m:
            break
        inner = m.group(1)
        count = int(m.group(2)) if m.group(2) else 1
        try:
            comp = parse_formula(inner)
            expanded = ""
            for el, val in comp.as_dict.items():
                v = val * count
                expanded += f"{el}{v:g}" if v != 1 else el
            formula = formula.replace(m.group(0), expanded)
        except Exception:
            break
        iteration += 1
    
    return formula


def get_g_crc(cur, formula):
    """Ищет dGf в CRC по формуле (пробует все фазы)."""
    for ph in ('aq', 'l', 'g', 's'):
        row = cur.execute(
            "SELECT dGf FROM species WHERE formula = ? AND phase = ?",
            (formula, ph)
        ).fetchone()
        if row:
            return row[0]
    return None


def parse_reaction_side(side_str):
    """Разбирает сторону реакции на список (формула, коэффициент)."""
    parts = side_str.split(" + ")
    res = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        tokens = p.split(maxsplit=1)
        if tokens[0].isdigit():
            coeff = int(tokens[0])
            formula = tokens[1] if len(tokens) > 1 else ""
            res.append((clean_formula_complex(formula), coeff))
        else:
            res.append((clean_formula_complex(p), 1))
    return res


def check_balance(left_list, right_list):
    """Проверяет баланс элементов и заряда."""
    elements_left, charge_left = {}, 0
    for f, c in left_list:
        try:
            comp = parse_formula(f)
            for el, val in comp.as_dict.items():
                elements_left[el] = elements_left.get(el, 0.0) + val * c
            charge_left += comp.charge * c
        except Exception:
            return False
    
    elements_right, charge_right = {}, 0
    for f, c in right_list:
        try:
            comp = parse_formula(f)
            for el, val in comp.as_dict.items():
                elements_right[el] = elements_right.get(el, 0.0) + val * c
            charge_right += comp.charge * c
        except Exception:
            return False
    
    if abs(charge_left - charge_right) > 1e-6:
        return False
    if set(elements_left.keys()) != set(elements_right.keys()):
        return False
    for el in elements_left:
        if abs(elements_left[el] - elements_right[el]) > 1e-6:
            return False
    return True


def main():
    """Главная функция диагностики."""
    print("=" * 60)
    print("ДИАГНОСТИКА ПРОПУЩЕННЫХ РЕАКЦИЙ (W-26)")
    print("=" * 60)
    
    # Проверяем наличие файлов
    if not MANIFEST_PATH.exists():
        print(f" Manifest не найден: {MANIFEST_PATH}")
        return
    
    if not RAW_JSON_PATH.exists():
        print(f"❌ Raw JSON не найден: {RAW_JSON_PATH}")
        return
    
    if not CRC_PATH.exists():
        print(f"❌ CRC DB не найден: {CRC_PATH}")
        return
    
    # Загружаем manifest
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stats = manifest["stats"]
    
    print(f"\n📊 Статистика из manifest.json:")
    print(f"   Всего распарсено: {stats['total_parsed']}")
    print(f"   Добавлено: {stats['added']}")
    print(f"   Пропущено (CRC существует): {stats['skipped_crc_exists']}")
    print(f"   Пропущено (баланс): {stats['skipped_balance_fail']}")
    print(f"   Пропущено (нет реагентов): {stats['skipped_missing_reactants']}")
    print(f"   Пропущено (мастер): {stats['skipped_master']}")
    print(f"   Пропущено (прочее): {stats['skipped_other']}")
    
    # Загружаем raw JSON для анализа
    raw_data = json.loads(RAW_JSON_PATH.read_text(encoding="utf-8"))
    
    # Собираем мастер-формулы
    master_formulas = {s['master_formula'] for s in raw_data['master_species']}
    master_formulas.add("H2O")
    master_formulas.add("e-")
    master_formulas.add("H+")
    master_formulas.add("OH-")
    
    # Собираем формулы добавленных веществ из manifest
    added_formulas = {s['formula'] for s in manifest['new_species']}
    conflict_formulas = {c['formula'] for c in manifest['conflicts']}
    
    # Подключаемся к CRC
    con = sqlite3.connect(str(CRC_PATH))
    cur = con.cursor()
    
    # Анализируем пропущенные реакции
    balance_failed = []
    missing_reactants = []
    other_skipped = []
    
    for sp in raw_data["solution_species"]:
        reaction = sp["reaction"]
        left_str, right_str = reaction.split(" = ", 1)
        left = parse_reaction_side(left_str)
        right = parse_reaction_side(right_str)
        
        if len(right) != 1:
            continue
        
        product = right[0][0]
        
        # Проверяем, была ли реакция добавлена
        if product in added_formulas:
            continue
        
        # Проверяем, был ли конфликт
        if product in conflict_formulas:
            continue
        
        # Реакция пропущена - определяем причину
        if product in master_formulas:
            # Мастер-ион - это нормально
            continue
        
        if not check_balance(left, right):
            balance_failed.append({
                "reaction": reaction,
                "left": left,
                "right": right,
                "log_k": sp["log_k"]
            })
            continue
        
        # Проверяем наличие реагентов
        missing_f = None
        for f, c in left:
            g = get_g_crc(cur, f)
            if g is None:
                missing_f = f
                break
        
        if missing_f:
            missing_reactants.append({
                "reaction": reaction,
                "missing": missing_f,
                "log_k": sp["log_k"]
            })
        else:
            other_skipped.append({
                "reaction": reaction,
                "log_k": sp["log_k"]
            })
    
    # Выводим результаты
    print(f"\n{'=' * 60}")
    print(f"АНАЛИЗ ПРОПУЩЕННЫХ РЕАКЦИЙ")
    print(f"{'=' * 60}")
    
    print(f"\n❌ Не сошелся баланс ({len(balance_failed)} реакций):")
    for item in balance_failed[:10]:
        print(f"   {item['reaction']} (log_k={item['log_k']})")
        print(f"      Left: {item['left']}")
        print(f"      Right: {item['right']}")
    
    print(f"\n❌ Не хватает реагентов в CRC ({len(missing_reactants)} реакций):")
    for item in missing_reactants[:10]:
        print(f"   Не найден [{item['missing']}] в: {item['reaction']} (log_k={item['log_k']})")
    
    print(f"\n️  Прочие пропуски ({len(other_skipped)} реакций):")
    for item in other_skipped[:10]:
        print(f"   {item['reaction']} (log_k={item['log_k']})")
    
    con.close()
    
    print(f"\n{'=' * 60}")
    print(f"ДИАГНОСТИКА ЗАВЕРШЕНА")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()