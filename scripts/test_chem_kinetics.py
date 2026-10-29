import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def main():
    agent = Agent(offline=True)

    # ТЕСТ 1: Гремучий газ (H2 + O2). Без искры не должен реагировать.
    print("=== ТЕСТ 1: Гремучий газ (без искры) ===")
    req1 = {
        "reagents": [
            {"formula": "H2", "moles": 2.0, "phase": "g"},
            {"formula": "O2", "moles": 1.0, "phase": "g"}
        ],
        "conditions": {"temperature_K": 400.0, "solvent": {"name": "none"}}
    }
    res1 = agent.predict(request=req1)
    print(f"Статус: {res1.data['status']}")
    print(f"Главный продукт: {res1.data.get('summary', {}).get('main_product')}")
    print(f"Сработавшие правила: {[r['id'] for r in res1.data.get('rules_fired', [])]}")
    
    # ТЕСТ 2: Разложение бертолетовой соли при нагреве (должно идти)
    print("\n=== ТЕСТ 2: KClO3 при 700 K ===")
    req2 = {
        "reagents": [{"formula": "KClO3", "moles": 1.0, "phase": "s"}],
        "conditions": {"temperature_K": 700.0, "solvent": {"name": "none"}}
    }
    res2 = agent.predict(request=req2)
    print(f"Статус: {res2.data['status']}")
    print(f"Главный продукт: {res2.data.get('summary', {}).get('main_product')}")
    if res2.data.get('balanced_equations'):
        print(f"Уравнение: {res2.data['balanced_equations'][0]['equation']}")

    # ТЕСТ 3: Восстановление цинком меди (быстрая реакция, не должна блокироваться кинетикой)
    print("\n=== ТЕСТ 3: Zn + CuSO4 ===")
    req3 = {
        "reagents": [
            {"formula": "Zn", "moles": 1.0, "phase": "s"},
            {"formula": "CuSO4", "moles": 1.0, "phase": "aq"}
        ],
        "conditions": {"temperature_K": 298.15, "solvent": {"name": "water"}, "volume_L": 1.0}
    }
    res3 = agent.predict(request=req3)
    print(f"Статус: {res3.data['status']}")
    print(f"Главный продукт: {res3.data.get('summary', {}).get('main_product')}")

if __name__ == "__main__":
    main()