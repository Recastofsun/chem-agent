import traceback
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def run_debug(name, request):
    print(f"\n=== ЗАПУСК: {name} ===")
    agent = Agent(offline=True)
    try:
        res = agent.predict(request=request)
        print(f"Статус: {res.data['status']}")
        if res.data['status'] == 'error':
            print(f"Сообщение об ошибке: {res.data.get('message')}")
            # Печатаем полный трейсбек из логов, если он есть
            print("Warnings:", res.data.get('warnings', []))
    except Exception as e:
        print(f"❌ УПАЛО С ИСКЛЮЧЕНИЕМ: {e}")
        traceback.print_exc()

# 1. Проблема с CaC2 (h067)
run_debug("h067 (CaC2 + H2O)", {
    "reagents": [
        {"formula": "CaC2", "moles": 0.01, "phase": "s"},
        {"formula": "H2O", "moles": 0.5, "phase": "l"}
    ],
    "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}},
    "options": {}
})

# 2. Проблема с Fe(SCN)3 (h049)
run_debug("h049 (FeCl3 + KSCN)", {
    "reagents": [
        {"formula": "FeCl3", "moles": 0.01, "phase": "aq"},
        {"formula": "KSCN", "moles": 0.03, "phase": "aq"}
    ],
    "conditions": {"temperature_K": 298.15, "volume_L": 1.0, "solvent": {"name": "water"}},
    "options": {}
})