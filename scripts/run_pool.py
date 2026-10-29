"""Прогон пула (ТЗ п. 13): точность по главному продукту и структурному уравнению.

python scripts/run_pool.py [data/pool_100.json]
-> data/pool_report.json (по каждой реакции), data/pool_disputed.json (несовпадения),
   строки отчета в консоли. Главный продукт - summary.main_product (первый), сравнение по составу.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chem_agent.agent import Agent  # noqa: E402
from chem_agent.benchmark import equations_match  # noqa: E402
from chem_agent.parser.formula import parse_formula  # noqa: E402

OPTS = {"include_uncertainty": False, "include_kinetics": False}


def run(path: Path) -> dict:
    pool = json.loads(path.read_text(encoding="utf-8"))
    agent = Agent()
    rows, t0 = [], time.perf_counter()
    for rx in pool:
        try:
            d = agent.predict(reagents=rx["reagents"], conditions=rx["conditions"], options=OPTS).data
            main = (d.get("summary") or {}).get("main_product")
            eq = ((d.get("balanced_equations") or [{}])[0]).get("equation")
            status, err = d.get("status"), d.get("message") if d.get("status") in ("error", "unknown") else None
        except Exception as e:  # noqa: BLE001
            main, eq, status, err = None, None, "exception", f"{type(e).__name__}: {e}"
        accept = [rx["expected_main"]] + rx.get("accept_main", [])
        main_ok = main is not None and any(parse_formula(main).key == parse_formula(a).key for a in accept)
        eq_ok = any(equations_match(e, eq) for e in [rx["expected_equation"]] + rx.get("accept_equations", []))
        rows.append({"id": rx["id"], "category": rx["category"], "status": status, "main": main,
                     "expected_main": rx["expected_main"], "main_ok": main_ok, "equation": eq,
                     "expected_equation": rx["expected_equation"], "equation_ok": eq_ok,
                     "ok": main_ok and eq_ok, "error": err})
    n = len(rows)
    rep = {"pool": str(path.relative_to(ROOT)), "n": n,
           "accuracy": sum(r["ok"] for r in rows) / n,
           "main_accuracy": sum(r["main_ok"] for r in rows) / n,
           "equation_accuracy": sum(r["equation_ok"] for r in rows) / n,
           "by_category": {}, "time_s": round(time.perf_counter() - t0, 1), "rows": rows}
    for c in sorted({r["category"] for r in rows}):
        rr = [r for r in rows if r["category"] == c]
        rep["by_category"][c] = round(sum(r["ok"] for r in rr) / len(rr), 3)
    return rep


def main():
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "data" / "pool_100.json"
    rep = run(path)
    stem = path.stem.replace("pool_", "")
    (ROOT / "data" / f"pool_report_{stem}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in rep["rows"] if not r["ok"]]
    print(f"Точность (продукт и уравнение): {rep['accuracy']:.1%}; продукт {rep['main_accuracy']:.1%}; "
          f"уравнение {rep['equation_accuracy']:.1%}; {rep['n']} реакций, {rep['time_s']} с")
    for c, a in rep["by_category"].items():
        print(f"  {c:14s} {a:.0%}")
    for r in bad:
        print(f"  x {r['id']}: {r['main']} | {r['equation']}\n      ожидалось {r['expected_main']} | {r['expected_equation']}"
              + (f"\n      {r['error']}" if r["error"] else ""))


if __name__ == "__main__":
    main()
