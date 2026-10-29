import json

with open('data/pool_1000_excluded.json', encoding='utf-8') as f:
    ex = json.load(f)

print(f"Всего исключено: {len(ex)}\n")
for r in ex[:15]:
    print(f"{r['id']} ({r['category']}) -> не хватает: {r.get('missing')}")