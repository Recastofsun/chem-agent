"""Детальная отладка одной реакции."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
from chem_agent.agent import Agent

def debug_reaction(r_id: str):
    with open(ROOT / "data" / "pool_1000.json", 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    pool_dict = {r["id"]: r for r in pool}
    reaction = pool_dict.get(r_id)
    
    if not reaction:
        print(f"❌ Реакция {r_id} не найдена")
        return
    
    print(f"\n{'='*80}")
    print(f"Реакция: {r_id}")
    print(f"{'='*80}")
    print(f"Реагенты: {json.dumps(reaction.get('reagents'), ensure_ascii=False, indent=2)}")
    print(f"Ожидаемый продукт: {reaction.get('expected_main')}")
    print(f"Условия: {json.dumps(reaction.get('conditions'), ensure_ascii=False, indent=2)}")
    
    agent = Agent(offline=True)
    
    conditions = {"solvent": "water", "volume_L": 1.0}
    if "conditions" in reaction and "temperature_K" in reaction["conditions"]:
        conditions["temperature_K"] = reaction["conditions"]["temperature_K"]
    
    request = {
        "reagents": reaction["reagents"],
        "conditions": conditions,
        "options": {"accuracy": "fast", "include_uncertainty": False}
    }
    
    print(f"\n🔬 Запуск модели...")
    result = agent.predict(request=request)
    data = result.data
    
    if data.get("status") == "error":
        print(f"❌ Ошибка: {data.get('message')}")
        return
    
    print(f"\n📊 Результаты:")
    print(f"   Статус: {data.get('status')}")
    print(f"   Реакция идет: {data.get('reaction_occurred')}")
    
    products = data.get("products", [])
    if products:
        print(f"\n   Продукты (топ-5):")
        for i, p in enumerate(products[:5], 1):
            print(f"      {i}. {p['formula']}: {p['moles']:.4g} моль")
    
    summary = data.get("summary", {})
    if summary.get("delta_G_kJ_mol") is not None:
        print(f"\n   ΔG = {summary['delta_G_kJ_mol']:.1f} кДж/моль")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    # Пример: отладка реакции c10
    debug_reaction("c10")
    # Или реакции термического разложения
    # debug_reaction("d10")