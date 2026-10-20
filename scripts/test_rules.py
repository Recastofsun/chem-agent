import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chem_agent.agent import Agent

def run_test(name: str, request: dict, expected_status: str, check_func=None):
    print(f"\n--- ТЕСТ: {name} ---")
    agent = Agent(offline=True)
    try:
        res = agent.predict(request=request)
        print(f"Статус: {res.data['status']}")
        
        eq = res.data.get("balanced_equations", [])
        if eq:
            print(f"Уравнение: {eq[0]['equation']}")
            print(f"ΔG: {eq[0]['delta_G_kJ_mol']:.1f} кДж/моль" if eq[0]['delta_G_kJ_mol'] else "ΔG: —")
        else:
            print("Уравнение: не найдено")
            
        # Выводим предупреждения, если статус не тот, который ждали
        if res.data['status'] != expected_status:
            print("Предупреждения (Warnings):")
            for w in res.data.get("warnings", []):
                print(f" - {w}")
        
        if res.data['status'] == expected_status:
            print("✅ Статус совпал с ожидаемым")
        else:
            print(f"❌ ОШИБКА: Ожидался статус '{expected_status}', получен '{res.data['status']}'")
            
        if check_func:
            check_func(res.data)
            
    except Exception as e:
        print(f"❌ Исключение: {e}")
        traceback.print_exc()

def main():
    run_test(
        "h049 (FeCl3 + KSCN) - блокировка ложного редокса",
        {
            "reagents": [
                {"formula": "FeCl3", "moles": 0.001},
                {"formula": "KSCN", "moles": 0.001}
            ],
            "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "atmosphere": {"mode": "closed"}},
            "known_energies": {}, "constraints": {}, "options": {}
        },
        expected_status="no_reaction"
    )

    # Остальные тесты оставляем без изменений...
    run_test(
        "h054 (KNO3) в закрытой системе при 700 K",
        {
            "reagents": [{"formula": "KNO3", "moles": 1.0}],
            "conditions": {"temperature_K": 700, "volume_L": 1.0, "atmosphere": {"mode": "closed"}},
            "known_energies": {}, "constraints": {}, "options": {}
        },
        expected_status="no_reaction"
    )

    run_test(
        "h054 (KNO3) в открытой системе при 700 K",
        {
            "reagents": [{"formula": "KNO3", "moles": 1.0}],
            "conditions": {"temperature_K": 700, "volume_L": 1.0, "atmosphere": {"mode": "open"}},
            "known_energies": {}, "constraints": {}, "options": {}
        },
        expected_status="ok",
        check_func=lambda data: print("Продукты:", [p['formula'] for p in data.get('products', [])])
    )

    run_test(
        "Контроль (Zn + HCl)",
        {
            "reagents": [
                {"formula": "Zn", "moles": 0.1, "phase": "s"},
                {"formula": "HCl", "moles": 0.2}
            ],
            "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "atmosphere": {"mode": "closed"}},
            "known_energies": {}, "constraints": {}, "options": {}
        },
        expected_status="ok"
    )

if __name__ == "__main__":
    main()