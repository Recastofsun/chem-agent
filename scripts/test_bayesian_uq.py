import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent
import json

def main():
    agent = Agent(offline=True)
    
    # Реакция осаждения с известной неопределенностью
    req = {
        "reagents": [
            {"formula": "CaCl2", "moles": 0.05, "phase": "aq"},
            {"formula": "Na2CO3", "moles": 0.05, "phase": "aq"}
        ],
        "conditions": {"temperature_K": 298.15, "solvent": {"name": "water"}, "volume_L": 1.0},
        "options": {"include_uncertainty": True, "uncertainty_method": "ensemble", "accuracy": "balanced"}
    }
    
    res = agent.predict(request=req)
    s = res.data.get("summary", {})
    
    print("=== Байесовский анализ неопределенности (W-35) ===")
    print(f"Главный продукт: {s.get('main_product')}")
    print(f"Моли продукта: {s.get('main_product_moles_95_CI')} (95% CI)")
    print(f"ΔG реакции: {s.get('delta_G_kJ_mol'):.1f} кДж/моль")
    print(f"ΔG 95% CI: {s.get('delta_G_95_CI')}")
    print(f"pH раствора: {s.get('pH'):.2f}")
    print(f"pH 95% CI: {s.get('pH_95_CI')}")
    
    # Красивый вывод для проверки
    if s.get("pH_95_CI"):
        print(f"\nИнженерный вывод: pH = {s['pH']:.2f} (95% ДИ: {s['pH_95_CI'][0]:.2f} — {s['pH_95_CI'][1]:.2f})")

if __name__ == "__main__":
    main()