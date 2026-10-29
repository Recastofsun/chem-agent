import json

with open('data/pool_disputed_1000.json', encoding='utf-8') as f:
    disputed = json.load(f)

unparsed = [r['id'] for r in disputed if r['reason'] == 'не разобрано']
print(f"Реакции без причины: {unparsed}")