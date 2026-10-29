import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.energy.database import get_db
from chem_agent.electrochem.kinetics import select_dominant_reaction

def main():
    db = get_db()
    T = 298.15
    
    # --- ТЕСТ 1: HCl при 1.5 В ---
    print("=== Тест 1: HCl при 1.5 В ===")
    conc_hcl = {"H+": 0.1, "Cl-": 0.1, "H2O": 55.5}
    
    # Анод (окисление)
    res_an = select_dominant_reaction(db, U=1.5, concentrations=conc_hcl, T=T, side="anode")
    print("АНОД (ожидаем Cl2):")
    if res_an:
        print(f"  Победила: {res_an['ox']} / {res_an['red']}")
        print(f"  E_eq={res_an['E_eq']:.2f} В, eta={res_an['eta']:.2f} В")
    else:
        print("  Реакции нет")

    # Катод (восстановление)
    res_cat = select_dominant_reaction(db, U=1.5, concentrations=conc_hcl, T=T, side="cathode")
    print("КАТОД (ожидаем H2):")
    if res_cat:
        print(f"  Победила: {res_cat['ox']} / {res_cat['red']}")
        print(f"  E_eq={res_cat['E_eq']:.2f} В, eta={res_cat['eta']:.2f} В")
    else:
        print("  Реакции нет")

    # --- ТЕСТ 2: Na2SO4 при 1.5 В ---
    print("\n=== Тест 2: Na2SO4 при 1.5 В ===")
    conc_na = {"Na+": 0.1, "SO4-2": 0.1, "H2O": 55.5}
    
    res_an2 = select_dominant_reaction(db, U=1.5, concentrations=conc_na, T=T, side="anode")
    print("АНОД (ожидаем отсутствие реакции, так как O2 заблокирован перенапряжением):")
    if res_an2:
        print(f"  Победила: {res_an2['ox']} / {res_an2['red']}")
    else:
        print("  Реакции нет (ПРАВИЛЬНО)")

    # --- ТЕСТ 3: Na2SO4 при 2.5 В ---
    print("\n=== Тест 3: Na2SO4 при 2.5 В ===")
    res_an3 = select_dominant_reaction(db, U=2.5, concentrations=conc_na, T=T, side="anode")
    print("АНОД (ожидаем O2):")
    if res_an3:
        print(f"  Победила: {res_an3['ox']} / {res_an3['red']}")
        print(f"  E_eq={res_an3['E_eq']:.2f} В, eta={res_an3['eta']:.2f} В")
    else:
        print("  Реакции нет")

if __name__ == "__main__":
    main()