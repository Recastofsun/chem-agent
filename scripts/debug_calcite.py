import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from chem_agent.agent import Agent

agent = Agent(offline=True)
bench = json.loads(Path("tests/fixtures/phreeqc_benchmark.json").read_text(encoding="utf-8"))
case = next(c for c in bench if c["id"] == "phreeqc_02_calcite")

req = {"reagents": case["reagents"], "conditions": case["conditions"]}
res = agent.predict(request=req)
data = res.data

fc = data.get("final_composition", [])
water_kg = sum(p["final_mol"] for p in fc if p["formula"] == "H2O" and p["phase"] == "l") * 0.018015268
print(f"Вода: {water_kg:.4g} кг\n")

for p in fc:
    if p["phase"] == "aq" and p["final_mol"] > 0:
        molality = p["final_mol"] / water_kg
        if "Ca" in p["formula"] or "C" in p["formula"]:
            print(f"{p['formula']:<15} {molality:.5g} моль/кг")

# Считаем общий кальций
total_ca = sum(p["final_mol"] / water_kg for p in fc if p["phase"] == "aq" and "Ca" in p["formula"])
print(f"\nОбщий кальций (сумма): {total_ca:.5g} моль/кг (PHREEQC ожидает 0.00146)")