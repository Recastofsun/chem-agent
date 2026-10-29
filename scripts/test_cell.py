import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def main():
    agent = Agent(offline=True)
    req = {
        "cell": {
            "anode": {
                "electrode": {"material": "Pt"},
                "solution": {"species": [{"formula": "NaCl", "moles": 0.1}]}
            },
            "cathode": {
                "electrode": {"material": "Cu"},
                "solution": {"species": [{"formula": "CuSO4", "moles": 0.1}]}
            },
            "membrane": {"type": "cation_exchange"},
            "external_circuit": {"mode": "potentiostatic", "voltage_V": 2.0}
        }
    }
    
    res = agent.predict(request=req)
    print("Статус:", res.data["status"])
    
    if res.data["status"] == "error":
        print("Ошибка:", res.data.get("message"))
    else:
        print("Анод:", res.data["cell_result"]["anode"])
        print("Катод:", res.data["cell_result"]["cathode"])

if __name__ == "__main__":
    main()