"""Тестирование электролиза на разных системах."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def run_test(name, request, expected_products):
    print(f"\n=== ТЕСТ: {name} ===")
    agent = Agent(offline=True)
    try:
        res = agent.predict(request=request)
        data = res.data
        print(f"Статус: {data['status']}")
        
        if data.get('balanced_equations'):
            print(f"Уравнение: {data['balanced_equations'][0]['equation']}")
        
        prods = [p['formula'] for p in data.get('products', [])[:4]]
        print(f"Продукты (top-4): {prods}")
        
        # Проверяем, что целевые продукты есть в списке (игнорируя статус unreliable)
        found = all(p in prods for p in expected_products)
        if found and data['status'] in ('ok', 'unreliable'):
            print("✅ Успешно: целевые продукты найдены")
        else:
            print(f"❌ Ожидались продукты: {expected_products}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def main():
    # Тест 1: Электролиз CuCl2 (1.5 В)
    run_test(
        "Электролиз CuCl2 (1.5 В) -> Cu + Cl2",
        {
            "reagents": [{"formula": "CuCl2", "moles": 0.1, "phase": "aq"}],
            "conditions": {
                "temperature_K": 298.15, 
                "electrolysis": {"enabled": True, "voltage_V": 1.5}
            }
        },
        expected_products=["Cu", "Cl2"]
    )

    # Тест 2: Электролиз HCl (2.0 В)
    run_test(
        "Электролиз HCl (2.0 В) -> H2 + Cl2",
        {
            "reagents": [{"formula": "HCl", "moles": 0.1, "phase": "aq"}],
            "conditions": {
                "temperature_K": 298.15, 
                "electrolysis": {"enabled": True, "voltage_V": 2.0}
            }
        },
        expected_products=["H2", "Cl2"]
    )

    # Тест 3: Электролиз Na2SO4 (3.0 В) -> Na2S2O8 + H2
    run_test(
        "Электролиз Na2SO4 (3.0 В) -> Na2S2O8",
        {
            "reagents": [{"formula": "Na2SO4", "moles": 0.1, "phase": "aq"}],
            "conditions": {
                "temperature_K": 298.15, 
                "electrolysis": {"enabled": True, "voltage_V": 3.0}
            }
        },
        expected_products=["Na2S2O8", "H2"] # Или S2O8-2
    )

if __name__ == "__main__":
    main()