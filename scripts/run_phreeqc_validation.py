import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from chem_agent.agent import Agent

def main():
    agent = Agent(offline=True, db_path='chem_agent/data/phreeqc.db')
    bench_file = Path(__file__).parent.parent / "tests" / "fixtures" / "phreeqc_benchmark.json"
    cases = json.loads(bench_file.read_text(encoding="utf-8"))

    print(f"{'ID':<25} | {'Параметр':<15} | {'Ожидалось':<12} | {'Получено (отклонение)':<25}")
    print("-" * 85)

    for case in cases:
        cid = case["id"]
        ctype = case["type"]
        
        if ctype == "electrolysis":
            req = {"cell": case["cell"]}
        else:
            req = {"reagents": case["reagents"], "conditions": case.get("conditions", {})}
        
        try:
            res = agent.predict(request=req)
            data = res.data
            
            if data.get("status") == "error":
                print(f"{cid:<25} | ОШИБКА: {data.get('message')}")
                continue

            if ctype == "electrolysis":
                # ВЫВОДИМ ПРЕДУПРЕЖДЕНИЯ, ЧТОБЫ УВИДЕТЬ РАБОТУ КИНЕТИКИ
                print(f"{cid:<25} | СТАТУС: {data['status']} | {data.get('warnings', [])}")
                
                anode_species = {s["formula"]: s["moles"] for s in data["cell_result"]["anode"]["species"]}
                cathode_species = {s["formula"]: s["moles"] for s in data["cell_result"]["cathode"]["species"]}
                
                for side, species_dict in [("anode", anode_species), ("cathode", cathode_species)]:
                    for key, exp_val in case["expected"][side].items():
                        act_val = species_dict.get(key, 0.0)
                        rel_err = abs(act_val - exp_val) / max(exp_val, 1e-9) if exp_val else 0
                        print(f"{cid:<25} | {side}:{key:<12} | {exp_val:<12.4g} | {act_val:.4g} (откл. {rel_err:.1%})")
            
            else:
                # ФИКС: Ищем в final_composition
                # PHREEQC отдает моляльность: растворенные частицы делим на массу оставшейся воды
                # (гипс связывает 2 H2O на моль, вода убывает).
                fc = data.get("final_composition", [])
                water_kg = sum(p["final_mol"] for p in fc if p["formula"] == "H2O" and p["phase"] == "l") * 0.018015268
                comp = {p["formula"]: p["final_mol"] / water_kg if p["phase"] == "aq" and water_kg > 0 else p["final_mol"]
                        for p in fc}
                summary = data.get("summary", {})
                
                for key, exp_val in case["expected"].items():
                    clean_key = key.split("(")[0].strip()
                    
                    if clean_key in comp:
                        act_val = comp[clean_key]
                    elif key == "pH":
                        act_val = summary.get("pH")
                    elif key == "ionic_strength":
                        act_val = summary.get("ionic_strength_M")
                    else:
                        act_val = summary.get("main_product")
                    
                    if isinstance(act_val, (int, float)) and exp_val:
                        rel_err = abs(act_val - exp_val) / max(abs(exp_val), 1e-9)
                        print(f"{cid:<25} | {key:<15} | {exp_val:<12.4g} | {act_val:.4g} (откл. {rel_err:.1%})")
                    else:
                        print(f"{cid:<25} | {key:<15} | {exp_val:<12.4g} | {act_val}")

        except Exception as e:
            print(f"{cid:<25} | ИСКЛЮЧЕНИЕ: {e}")

if __name__ == "__main__":
    main()