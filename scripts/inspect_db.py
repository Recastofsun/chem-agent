import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chem_agent.energy.database import get_db
from chem_agent.parser.formula import parse_formula
from chem_agent.search.rules import RuleContext, evaluate
from chem_agent.parser import classifier

def main():
    db = get_db()
    print("="*50)
    print("1. ПРОВЕРКА НАЛИЧИЯ В БАЗЕ (crc.db)")
    print("="*50)
    
    for formula in ["C2H2", "Fe(SCN)3", "FeSO4", "CaC2"]:
        comp = parse_formula(formula)
        species = db.find(comp)
        if not species:
            print(f"❌ {formula}: НЕ НАЙДЕН в базе данных!")
        else:
            for s in species:
                print(f"✅ {formula} ({s.phase}): dGf = {s.dGf} кДж/моль, source = {s.source}")

    print("\n" + "="*50)
    print("2. ПРОВЕРКА КЛАССИФИКАТОРА")
    print("="*50)
    comps = {
        "C2H2": parse_formula("C2H2"),
        "SCN-": parse_formula("SCN-"),
        "SO4-2": parse_formula("SO4-2"),
        "FeSO4": parse_formula("FeSO4"),
    }
    for name, comp in comps.items():
        print(f"{name}: alkane={classifier.is_alkane(comp)}, alkene={classifier.is_alkene(comp)}, alkyne={classifier.is_alkyne(comp)}, thiocyanate={classifier.is_thiocyanate(comp)}")

    print("\n" + "="*50)
    print("3. ПРИМЕНЕНИЕ ПРАВИЛ")
    print("="*50)
    # Симулируем правила для h067 (CaC2)
    ctx1 = RuleContext(T=298.15, aqueous=True, volume_L=1.0, reagents=[
        # Симулируем реагенты
    ])
    
    # Мы не можем легко вызвать evaluate без полного набора реагентов, 
    # поэтому просто посмотрим, какие правила вообще срабатывают на C2H2.
    print("Класс 'alkyne' запрещен в текущих правилах?")
    from chem_agent.search.rules import load_rules
    for rule in load_rules():
        if "carbide_hydrolysis_acetylene" in rule["id"]:
            print(f"Правило {rule['id']} запрещает: {rule['then'].get('forbid_new_class')}")

if __name__ == "__main__":
    main()