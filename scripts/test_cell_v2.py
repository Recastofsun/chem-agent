import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def run_test(name, cell_req):
    print(f"\n=== ТЕСТ: {name} ===")
    agent = Agent(offline=True)
    try:
        res = agent.predict(request={"cell": cell_req})
        data = res.data
        
        if data["status"] == "error":
            print(f"❌ Ошибка: {data.get('message')}")
            return

        print(f"Статус: {data['status']}")
        
        # Фильтруем вывод для красоты (показываем только > 0.001 моль)
        def print_side(side_name, side_data):
            print(f"--- {side_name} ---")
            for s in side_data["species"]:
                if s["moles"] > 1e-3:
                    print(f"  {s['formula']} ({s['phase']}): {s['moles']:.4f} моль")

        print_side("АНОД (окисление)", data["cell_result"]["anode"])
        print_side("КАТОД (восстановление)", data["cell_result"]["cathode"])
        
    except Exception as e:
        print(f"❌ Исключение: {e}")
        import traceback
        traceback.print_exc()

def main():
    # Тест 1: Электролиз воды (Na2SO4 как электролит)
    # Подаем 2.5 В, чтобы превысить потенциал разложения воды (1.23 В + перенапряжение)
    run_test(
        "Электролиз воды (Na2SO4)",
        {
            "anode": {
                "electrode": {"material": "Pt"},
                "solution": {"species": [{"formula": "Na2SO4", "moles": 0.1}]}
            },
            "cathode": {
                "electrode": {"material": "Pt"},
                "solution": {"species": [{"formula": "Na2SO4", "moles": 0.1}]}
            },
            "membrane": {"type": "cation_exchange"},
            "external_circuit": {"mode": "potentiostatic", "voltage_V": 1.5}
        }
    )

    # Тест 2: Электролиз HCl (получение водорода и хлора)
    # Подаем 1.5 В (достаточно для хлора 1.36 В, но мало для воды)
    run_test(
        "Электролиз HCl",
        {
            "anode": {
                "electrode": {"material": "C"},
                "solution": {"species": [{"formula": "HCl", "moles": 0.1}]}
            },
            "cathode": {
                "electrode": {"material": "C"},
                "solution": {"species": [{"formula": "HCl", "moles": 0.1}]}
            },
            "membrane": {"type": "cation_exchange"},
            "external_circuit": {"mode": "potentiostatic", "voltage_V": 1.5}
        }
    )
    # Тест 3: Электролиз HCl (получение водорода и хлора)
    run_test(
            "Электролиз HCl",
            {
                "anode": {
                    "electrode": {"material": "C"},
                    "solution": {"species": [{"formula": "HCl", "moles": 0.1}]}
                },
                "cathode": {
                    "electrode": {"material": "C"},
                    "solution": {"species": [{"formula": "HCl", "moles": 0.1}]}
                },
                "membrane": {"type": "cation_exchange"},
                "external_circuit": {"mode": "potentiostatic", "voltage_V": 2.0}
            }
        )
    

if __name__ == "__main__":
    main()