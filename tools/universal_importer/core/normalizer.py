"""Нормализация химических формул и реакций."""
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from chem_agent.parser.formula import parse_formula


def clean_formula_complex(formula: str) -> str:
    """
    Нормализует формулу водного комплекса БЕЗ раскрытия скобок.
    Сохраняет читаемость: Cu(CO3)2-2, Fe(SO4)2- и т.д.
    """
    if not formula:
        return formula
    
    # Базовая очистка
    formula = formula.replace("  ", " ").replace(": ", "·").replace(":", "·").strip()
    
    # Нормализация зарядов: ++ → +2, --- → -3
    m_charge = re.search(r'([+-]{2,})$', formula)
    if m_charge:
        sign = m_charge.group(1)[0]
        count = len(m_charge.group(1))
        formula = formula[:m_charge.start()] + f"{sign}{count}"
    
    # ВАЖНО: НЕ раскрываем скобки для комплексов!
    # Cu(CO3)2-2 остаётся Cu(CO3)2-2, а не CuC2O6-2
    
    return formula


def clean_formula_mineral(formula: str) -> str:
    """
    Нормализует формулу минерала С раскрытием скобок.
    Для минералов важна эмпирическая формула: CaCO3, не Ca(CO3).
    """
    if not formula:
        return formula
    
    # Базовая очистка
    formula = formula.replace("  ", " ").replace(": ", "·").replace(":", "·").strip()
    
    # Нормализация зарядов
    m_charge = re.search(r'([+-]{2,})$', formula)
    if m_charge:
        sign = m_charge.group(1)[0]
        count = len(m_charge.group(1))
        formula = formula[:m_charge.start()] + f"{sign}{count}"
    
    # Расширение скобок (только для минералов)
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


def clean_formula(formula: str, is_mineral: bool = False) -> str:
    """
    Универсальная функция нормализации.
    
    Args:
        formula: химическая формула
        is_mineral: True для минералов (раскрывать скобки), False для комплексов
    """
    if is_mineral:
        return clean_formula_mineral(formula)
    else:
        return clean_formula_complex(formula)


def parse_reaction_side(side_str: str) -> list[tuple[str, int]]:
    """Разбирает сторону реакции на список (формула, коэффициент)."""
    parts = side_str.split(" + ")
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        tokens = p.split(maxsplit=1)
        if tokens[0].isdigit():
            coeff = int(tokens[0])
            formula = tokens[1] if len(tokens) > 1 else ""
            result.append((clean_formula_complex(formula), coeff))
        else:
            result.append((clean_formula_complex(p), 1))
    return result


def check_balance(left: list[tuple[str, int]], right: list[tuple[str, int]]) -> bool:
    """
    Проверяет баланс элементов и заряда.
    Возвращает True если реакция сбалансирована.
    """
    el_left, q_left = {}, 0
    for f, c in left:
        try:
            comp = parse_formula(f)
            for k, v in comp.as_dict.items():
                el_left[k] = el_left.get(k, 0.0) + v * c
            q_left += comp.charge * c
        except Exception:
            return False
    
    el_right, q_right = {}, 0
    for f, c in right:
        try:
            comp = parse_formula(f)
            for k, v in comp.as_dict.items():
                el_right[k] = el_right.get(k, 0.0) + v * c
            q_right += comp.charge * c
        except Exception:
            return False
    
    if abs(q_left - q_right) > 1e-6:
        return False
    if set(el_left.keys()) != set(el_right.keys()):
        return False
    return all(abs(el_left[k] - el_right[k]) < 1e-6 for k in el_left)