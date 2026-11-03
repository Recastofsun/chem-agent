"""Проверка и исправление dGf для хлоридов железа."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chem_agent" / "data" / "crc.db"

def check_and_fix():
    if not DB_PATH.exists():
        print(f"❌ База не найдена: {DB_PATH}")
        return
    
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    
    print("=" * 70)
    print("ТЕКУЩИЕ ЗНАЧЕНИЯ dGf в БД:")
    print("=" * 70)
    
    formulas = ['FeCl2', 'FeCl3', 'Fe+2', 'Fe+3']
    values = {}
    
    for formula in formulas:
        cur.execute("SELECT dGf, source FROM species WHERE formula = ? AND phase = 'aq'", (formula,))
        result = cur.fetchone()
        if result:
            dGf, source = result
            values[formula] = dGf
            print(f"  {formula}(aq): dGf = {dGf:8.2f} кДж/моль (источник: {source})")
        else:
            print(f"  {formula}(aq): НЕ НАЙДЕН")
    
    print("\n" + "=" * 70)
    print("РАСЧЁТНЫЕ ЗНАЧЕНИЯ (из ионов):")
    print("=" * 70)
    
    # Получаем значения ионов
    cur.execute("SELECT dGf FROM species WHERE formula = 'Fe+2' AND phase = 'aq'")
    fe2 = cur.fetchone()
    cur.execute("SELECT dGf FROM species WHERE formula = 'Fe+3' AND phase = 'aq'")
    fe3 = cur.fetchone()
    cur.execute("SELECT dGf FROM species WHERE formula = 'Cl-' AND phase = 'aq'")
    cl = cur.fetchone()
    
    if fe2 and fe3 and cl:
        fe2_val, fe3_val, cl_val = fe2[0], fe3[0], cl[0]
        
        calc_fecl2 = fe2_val + 2 * cl_val
        calc_fecl3 = fe3_val + 3 * cl_val
        
        print(f"  Fe2+(aq): {fe2_val:8.2f} кДж/моль")
        print(f"  Fe3+(aq): {fe3_val:8.2f} кДж/моль")
        print(f"  Cl-(aq):  {cl_val:8.2f} кДж/моль")
        print(f"\n  FeCl2(aq) = Fe2+ + 2Cl- = {calc_fecl2:8.2f} кДж/моль")
        print(f"  FeCl3(aq) = Fe3+ + 3Cl- = {calc_fecl3:8.2f} кДж/моль")
        
        print("\n" + "=" * 70)
        print("РАЗЛИЧИЯ:")
        print("=" * 70)
        
        if 'FeCl2' in values:
            diff2 = values['FeCl2'] - calc_fecl2
            print(f"  FeCl2: текущее - расчётное = {diff2:+.2f} кДж/моль")
        if 'FeCl3' in values:
            diff3 = values['FeCl3'] - calc_fecl3
            print(f"  FeCl3: текущее - расчётное = {diff3:+.2f} кДж/моль")
        
        print("\n" + "=" * 70)
        print("РЕКОМЕНДАЦИЯ:")
        print("=" * 70)
        
        if abs(diff3) > 5.0:
            print(f"  ⚠️  FeCl3(aq) отличается на {diff3:+.2f} кДж/моль")
            print(f"  Это может приводить к неверным предсказаниям.")
            print(f"\n  Для исправления выполните:")
            print(f"  python scripts/patch_db_fix_fe_chlorides.py")
        else:
            print(f"  ✓ FeCl3(aq) в пределах допустимого отклонения")
    
    con.close()

if __name__ == "__main__":
    check_and_fix()