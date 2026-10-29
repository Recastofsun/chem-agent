"""Reference-set benchmark: Accuracy@k of the main product (tests/fixtures/reactions.json)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .parser.formula import parse_formula
from .utils.paths import PROJECT_DIR


def _keys_of_product(p: dict) -> set:
    out = {parse_formula(p["formula"]).key}
    for part in p.get("_parts_formulas", []):
        out.add(parse_formula(part).key)
    return out


def evaluate(agent, reactions: list[dict], k: int = 3, options: dict | None = None) -> dict:
    rows = []
    t0 = time.perf_counter()
    for rx in reactions:
        cond = {"temperature_K": rx["temperature_K"], "volume_L": rx.get("volume_L", 1.0),
                "solvent": rx.get("solvent", "water")}
        if "atmosphere" in rx:
            cond["atmosphere"] = rx["atmosphere"]
        opts = {"include_uncertainty": False, "include_kinetics": False, **(options or {})}
        try:
            res = agent.predict(reagents=rx["reagents"], conditions=cond, options=opts).data
            status = res["status"]
            prods = res["products"]
            err = None
        except Exception as e:  # noqa: BLE001
            status, prods, err = "error", [], f"{type(e).__name__}: {e}"
        top = prods[:k]
        exp = rx.get("expected_main")
        if exp is None:
            ok = status == "no_reaction"
        else:
            accept = rx.get("accept_any") or [exp]
            ek_set = {parse_formula(a).key for a in accept}
            ok = any(ek_set & _keys_of_product(p) for p in top) and status in ("ok", "unreliable")
        rows.append({"id": rx["id"], "category": rx["category"], "in_scope": rx.get("in_scope", True),
                     "ok": ok, "status": status, "expected": exp,
                     "top": [p["formula"] for p in top], "error": err})
    scoped = [r for r in rows if r["in_scope"]]
    acc = sum(r["ok"] for r in scoped) / max(1, len(scoped))
    by_cat: dict[str, list] = {}
    for r in scoped:
        by_cat.setdefault(r["category"], []).append(r["ok"])
    return {"accuracy_at_k": acc, "k": k, "n_in_scope": len(scoped), "n_total": len(rows),
            "by_category": {c: sum(v) / len(v) for c, v in by_cat.items()},
            "out_of_scope_ok": sum(r["ok"] for r in rows if not r["in_scope"]),
            "unreliable": sum(r["status"] == "unreliable" for r in scoped),
            "time_s": time.perf_counter() - t0, "rows": rows}


def load_reference(path: Path | None = None) -> list[dict]:
    p = path or PROJECT_DIR / "tests" / "fixtures" / "reactions.json"
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


# --- W-15: структурное сравнение уравнений (ТЗ 11.2) -------------------------------------------
_MARK = {"↓": "s", "↑": "g"}


def parse_equation(eq: str) -> dict:
    """"a A + b B -> c C↓ + d D↑" -> {(сторона, ключ состава, фаза-метка): коэффициент / НОД}.
    Метка: s (↓), g (↑), "" (раствор, жидкость). Формулы сравниваются по составу: NaCH3COO = CH3COONa."""
    from math import gcd
    out = {}
    left, right = eq.split("->")
    for side, part in (("L", left), ("R", right)):
        for term in part.split(" + "):
            term = term.strip()
            if not term:
                continue
            coef, _, f = term.partition(" ") if term.split(" ")[0].isdigit() else ("1", "", term)
            mark = ""
            if f and f[-1] in _MARK:
                mark, f = _MARK[f[-1]], f[:-1]
            out[(side, parse_formula(f.strip()).key, mark)] = out.get((side, parse_formula(f.strip()).key, mark), 0) + int(coef)
    g = 0
    for v in out.values():
        g = gcd(g, v)
    return {k: v // g for k, v in out.items()} if g else out


def equations_match(expected: str, actual: str | None) -> bool:
    if not actual:
        return False
    try:
        return parse_equation(expected) == parse_equation(actual)
    except Exception:  # noqa: BLE001
        return False
