import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def run_test(rid, name, request):
    agent = Agent(offline=True)
    res = agent.predict(request=request)
    data = res.data
    print(f"\n[{rid}] {name}")
    print(f"  Статус: {data['status']}")
    if data.get('balanced_equations'):
        print(f"  Уравнение: {data['balanced_equations'][0]['equation']}")
    prods = [p['formula'] for p in data.get('products', [])[:3]]
    print(f"  Продукты (top-3): {prods}")

def main():
    # h068: Na2CO3 в воде (ожидаем no_reaction, только гидролиз)
    run_test("h068", "Na2CO3 + H2O", {
        "reagents": [{"formula": "Na2CO3", "moles": 0.01, "phase": "aq"}],
        "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}
    })

    # h069: AlCl3 в воде (ожидаем no_reaction, слабый гидролиз)
    run_test("h069", "AlCl3 + H2O", {
        "reagents": [{"formula": "AlCl3", "moles": 0.01, "phase": "aq"}],
        "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}
    })

    # h086: NH3 + H2O (ожидаем no_reaction, растворение)
    run_test("h086", "NH3 + H2O", {
        "reagents": [{"formula": "NH3", "moles": 0.1, "phase": "g"}, {"formula": "H2O", "moles": 0.5, "phase": "l"}],
        "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}
    })

    # h094: K3[Fe(CN)6] + KOH (ожидаем no_reaction, комплекс стабилен)
    run_test("h094", "K3[Fe(CN)6] + KOH", {
        "reagents": [{"formula": "K3(Fe(CN)6)", "moles": 0.01, "phase": "aq"}, {"formula": "KOH", "moles": 0.02, "phase": "aq"}],
        "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}
    })

    # h095: Na2S2O3 + I2 (ожидаем Na2S4O6, но его нет в базе)
    run_test("h095", "Na2S2O3 + I2", {
        "reagents": [{"formula": "Na2S2O3", "moles": 0.05, "phase": "aq"}, {"formula": "I2", "moles": 0.01, "phase": "s"}],
        "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}}
    })

if __name__ == "__main__":
    main()