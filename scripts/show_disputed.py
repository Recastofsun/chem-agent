import json

with open('data/pool_disputed_1000.json', encoding='utf-8') as f:
    disputed = json.load(f)

print(f"Всего расхождений: {len(disputed)}\n")
for r in disputed:
    print(f"[{r['id']}] {r['category']}")
    print(f"  Ожидалось: {r['expected_main']} | Получено: {r['main']}")
    print(f"  Уравнение (ожидалось): {r.get('expected_equation')}")
    print(f"  Причина: {r.get('reason')}")
    print("-" * 40)