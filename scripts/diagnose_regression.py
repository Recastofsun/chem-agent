"""Диагностика: какие новые вещества влияют на расчёты."""
import json
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CRC_PATH = ROOT / "chem_agent" / "data" / "crc.db"
MANIFEST_PATH = ROOT / "tools" / "universal_importer" / "manifest.json"

def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    new_species = manifest["new_species"]
    
    print("=" * 60)
    print("ДИАГНОСТИКА: Анализ 131 нового вещества")
    print("=" * 60)
    
    # Группируем по типам
    acids_bases = []
    complexes = []
    minerals = []
    other = []
    
    for sp in new_species:
        formula = sp["formula"]
        phase = sp["phase"]
        
        # Кислоты/основания/простые соединения
        if formula in ["HCl", "HBr", "HI", "HNO3", "H2SO4", "H3PO4", "NH3", "NaOH", "KOH"]:
            acids_bases.append(sp)
        # Комплексы
        elif "(" in formula or "+" in formula or "-" in formula:
            complexes.append(sp)
        # Минералы
        elif phase == "s":
            minerals.append(sp)
        else:
            other.append(sp)
    
    print(f"\n Статистика:")
    print(f"   Кислоты/основания: {len(acids_bases)}")
    print(f"   Комплексы: {len(complexes)}")
    print(f"   Минералы: {len(minerals)}")
    print(f"   Прочие: {len(other)}")
    
    print(f"\n⚠️  Кислоты/основания (потенциально опасные):")
    for sp in acids_bases:
        print(f"   {sp['formula']}({sp['phase']}): dGf = {sp['dGf']} кДж/моль")
        print(f"      Реакция: {sp['source_reaction']}")
    
    # Проверяем, есть ли эти вещества уже в CRC
    con = sqlite3.connect(str(CRC_PATH))
    cur = con.cursor()
    
    print(f"\n🔍 Проверка конфликтов с CRC:")
    for sp in new_species:
        formula = sp["formula"]
        phase = sp["phase"]
        
        existing = cur.execute(
            "SELECT dGf, source FROM species WHERE formula = ? AND phase = ?",
            (formula, phase)
        ).fetchone()
        
        if existing:
            print(f"   ️  {formula}({phase}) УЖЕ ЕСТЬ в CRC: dGf={existing[0]}, source={existing[1]}")
            print(f"      В manifest: dGf={sp['dGf']}")
            print(f"      Разница: {abs(existing[0] - sp['dGf']):.2f} кДж/моль")
    
    con.close()

if __name__ == "__main__":
    main()