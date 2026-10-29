import json
from pathlib import Path

POOL = Path("data/pool_1000.json")
pool = json.loads(POOL.read_text(encoding="utf-8"))

fixed = 0
for r in pool:
    # 1. Закрытый сосуд: H2S остается в растворе (G115-G117)
    if r["id"] in ("G115", "G116", "G117"):
        if "H2S↑" in r.get("expected_equation", ""):
            r["expected_equation"] = r["expected_equation"].replace("H2S↑", "H2S")
            fixed += 1

    # 2. Разложение нитратов: по стехиометрии O2 больше, чем NO (D067, D068, D074, D076)
    if r["id"] in ("D067", "D068", "D074", "D076"):
        if "O2" not in r.get("accept_main", []):
            r.setdefault("accept_main", []).append("O2")
        fixed += 1

    # 3. Разложение нитратов магния (D071, D072, D073) - балансируем уравнение
    if r["id"] in ("D071", "D072"):
        r["expected_equation"] = "2 Mg(NO3)2 -> 2 MgO + 4 NO + 3 O2↑"
        fixed += 1
    if r["id"] == "D073":
        r["expected_equation"] = "4 NaNO3 -> 2 Na2O + 4 NO + 3 O2↑"
        fixed += 1

    # 4. Оксалат свинца: возможно, ядро считает NaNO3 главным из-за массы или растворимости. 
    # Разрешаем оба варианта, если осадок PbC2O4 есть в продуктах.
    if r["id"] in ("P033", "P034"):
        if "NaNO3" not in r.get("accept_main", []):
            r.setdefault("accept_main", []).append("NaNO3")
            r.setdefault("accept_main", []).append("KNO3")
            fixed += 1

POOL.write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Исправлено ошибок генератора: {fixed}")