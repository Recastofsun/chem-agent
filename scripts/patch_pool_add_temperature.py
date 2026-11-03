"""Добавление температуры для реакций термического разложения. """
import json
from pathlib import Path

POOL_PATH = Path(__file__).parent.parent / "data" / "pool_1000.json"

# Реакции термического разложения и их типичные температуры
THERMAL_DECOMPOSITION = {
    "d10": 743,      # Pb(NO3)2 → PbO + 2NO2 + ½O2 (~470°C)
    "D056": 873,     # KClO4 → KCl + 2O2 (~600°C)
    "D067": 713,     # AgNO3 → Ag + NO2 + ½O2 (~440°C)
    "D068": 713,     # AgNO3 (дубликат?)
    "D071": 623,     # Mg(NO3)2 → MgO + 2NO2 + ½O2 (~350°C)
    "D072": 623,     # Mg(NO3)2 (дубликат?)
    "D073": 653,     # NaNO3 → NaNO2 + ½O2 (~380°C)
    "D074": 653,     # NaNO3 (дубликат?)
    "D076": 673,     # KNO3 → KNO2 + ½O2 (~400°C)
}

def patch_pool():
    if not POOL_PATH.exists():
        print(f"❌ Файл не найден: {POOL_PATH}")
        return
    
    with open(POOL_PATH, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    updated = 0
    for reaction in pool:
        r_id = reaction.get("id")
        if r_id in THERMAL_DECOMPOSITION:
            if "conditions" not in reaction:
                reaction["conditions"] = {}
            reaction["conditions"]["temperature_K"] = THERMAL_DECOMPOSITION[r_id]
            updated += 1
            print(f"✓ {r_id}: добавлена температура {THERMAL_DECOMPOSITION[r_id]}K ({THERMAL_DECOMPOSITION[r_id]-273}°C)")
    
    with open(POOL_PATH, 'w', encoding='utf-8') as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Обновлено {updated} реакций")

if __name__ == "__main__":
    patch_pool()