"""Добавление недостающих веществ в crc.db (Категория 1 из pool_disputed_1000.json).
Значения ΔfG° рассчитаны из ионных данных NBS Tables (Wagman et al., 1982)."""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"


def compute_hill_formula(elements: dict) -> str:
    """Вычисляет формулу Хилла для сортировки."""
    if not elements:
        return ""
    c_count = elements.get("C", 0)
    h_count = elements.get("H", 0)
    others = {k: v for k, v in elements.items() if k not in ("C", "H")}
    result = []
    if "C" in elements:
        result.append(f"C{c_count if c_count != 1 else ''}")
    if "H" in elements:
        result.append(f"H{h_count if h_count != 1 else ''}")
    for el in sorted(others.keys()):
        count = others[el]
        result.append(f"{el}{count if count != 1 else ''}")
    return "".join(result)


# Вещества для добавления (точные значения из NBS Tables 1982)
SPECIES_TO_ADD = [
    # Сильные кислоты (полная диссоциация в воде)
    ("HCl", "aq", {"H": 1, "Cl": 1}, 0, -131.2, "NBS1982", 
     "Соляная кислота (H⁺ + Cl⁻ = 0 + (-131.2))"),
    ("H2SO4", "aq", {"H": 2, "S": 1, "O": 4}, 0, -744.5, "NBS1982", 
     "Серная кислота (2H⁺ + SO₄²⁻ = 0 + (-744.5))"),
    
    # Тиоцианат калия (SCN⁻: ΔfG° = +92.7 кДж/моль из таблицы)
    ("KSCN", "aq", {"K": 1, "S": 1, "C": 1, "N": 1}, 0, -190.6, "NBS1982", 
     "Тиоцианат калия (K⁺ + SCN⁻ = -283.3 + 92.7)"),
    
    # Нитрат свинца (II) (Pb²⁺: -24.4, NO₃⁻: -111.3)
    ("Pb(NO3)2", "s", {"Pb": 1, "N": 2, "O": 6}, 0, -246.9, "CRC97", 
     "Нитрат свинца (II), твердый"),
    ("Pb(NO3)2", "aq", {"Pb": 1, "N": 2, "O": 6}, 0, -247.0, "NBS1982", 
     "Нитрат свинца (II) (Pb²⁺ + 2NO₃⁻ = -24.4 + 2·(-111.3))"),
    
    # Оксалаты (C₂O₄²⁻: -673.9 кДж/моль из таблицы)
    ("Na2C2O4", "aq", {"Na": 2, "C": 2, "O": 4}, 0, -1197.7, "NBS1982", 
     "Оксалат натрия (2Na⁺ + C₂O₄²⁻ = 2·(-261.9) + (-673.9))"),
    ("K2C2O4", "aq", {"K": 2, "C": 2, "O": 4}, 0, -1240.5, "NBS1982", 
     "Оксалат калия (2K⁺ + C₂O₄²⁻ = 2·(-283.3) + (-673.9))"),
]


def add_species():
    if not DB_PATH.exists():
        print(f"❌ База не найдена: {DB_PATH}")
        return
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    added = 0
    skipped = 0
    
    for formula, phase, elements, charge, dGf, source, note in SPECIES_TO_ADD:
        existing = cur.execute(
            "SELECT formula FROM species WHERE formula = ? AND phase = ?",
            (formula, phase)
        ).fetchone()
        
        if existing:
            print(f"✓ {formula}({phase}) уже есть")
            skipped += 1
            continue
        
        hill = compute_hill_formula(elements)
        elements_json = json.dumps(elements)
        
        cur.execute(
            "INSERT INTO species (formula, phase, elements, charge, dGf, source, note, hill, sigma, dHf, S, Cp, dSf, name_en, name_ru) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (formula, phase, elements_json, charge, dGf, source, note, hill, 
            1.0,   # sigma (по умолчанию 1.0 кДж/моль)
            None,  # dHf
            None,  # S
            None,  # Cp
            None,  # dSf
            "",    # name_en
            None   # name_ru
            )
        )
        added += 1
        print(f"+ Добавлено: {formula}({phase}) dGf={dGf} кДж/моль ({note})")
    
    con.commit()
    con.close()
    
    print(f"\n✅ Итого: добавлено {added}, пропущено {skipped}")


if __name__ == "__main__":
    add_species()