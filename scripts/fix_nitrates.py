import json
from pathlib import Path

POOL = Path("data/pool_1000.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))

fixed = 0
for r in pool:
    if r["id"] in ("D067", "D068", "D071", "D072", "D073", "D074", "D076"):
        # Меняем ожидаемый главный продукт и уравнение на NO
        if r.get("expected_main") != "NO":
            r["expected_main"] = "NO"
            # Убираем NO2 из accept_main, если он там был
            if "accept_main" in r:
                r["accept_main"] = [p for p in r["accept_main"] if p != "NO2"]
            
            # Переписываем уравнение, чтобы оно соответствовало NO
            # (просто меняем NO2 на NO в тексте уравнения)
            if r.get("expected_equation"):
                r["expected_equation"] = r["expected_equation"].replace("NO2", "NO")
            
            fixed += 1

POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Обновлено реакций: {fixed}")