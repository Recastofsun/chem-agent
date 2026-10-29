"""Command line interface: chem-agent predict | self-test | benchmark | databases | version."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("CHEM_AGENT_OFFLINE", "1")

from . import __version__  # noqa: E402
from .utils import offline_guard  # noqa: E402

offline_guard.enable_from_env()


def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _parse_reagents(text: str, phase_default: str | None) -> list[dict]:
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            f, n = part.rsplit(":", 1)
            moles = float(n.replace(",", "."))
        else:
            f, moles = part, 1.0
        r = {"formula": f.strip(), "moles": moles}
        if phase_default:
            r["phase"] = phase_default
        out.append(r)
    return out


def cmd_predict(a) -> int:
    from .agent import Agent
    from .utils.encoding import read_json
    if a.input:
        req = read_json(Path(a.input))
    elif a.reagents:
        req = {"reagents": _parse_reagents(a.reagents, a.phase), "conditions": {}, "options": {}}
    else:
        print("Нужен --input файл.json или --reagents \"NaOH:2,H2SO4:1\"", file=sys.stderr)
        return 2
    cond = req.setdefault("conditions", {})
    if a.temp is not None:
        cond["temperature_K"] = a.temp
    if a.pressure is not None:
        cond["pressure_atm"] = a.pressure
    if a.volume is not None:
        cond["volume_L"] = a.volume
    if a.solvent is not None:
        cond["solvent"] = {"name": a.solvent}
    opts = req.setdefault("options", {})
    if a.output:
        opts["output_formats"] = [x.strip() for x in a.output.split(",")]
    if a.accuracy:
        opts["accuracy"] = a.accuracy
    if a.output_dir:
        opts["output_dir"] = a.output_dir
    if a.theme:
        opts["theme"] = a.theme
    if a.no_uncertainty:
        opts["include_uncertainty"] = False
    res = Agent().predict(request=req)
    d = res.data
    s = d.get("summary") or {}
    print(f"Статус: {d['status']}" + (f" - {d['message']}" if d.get("message") else ""))
    for e in d.get("balanced_equations") or []:
        dg = e.get("delta_G_kJ_mol")
        dg_s = "неизвестно" if dg is None else f"{dg:.1f} ± {e['delta_G_uncertainty']:.1f} кДж/моль"
        print(f"Уравнение: {e['equation']}   ΔG = {dg_s}")
    if d.get("ionic_equation"):
        print(f"Ионное:    {d['ionic_equation']['equation']}")
    for p in (d.get("products") or [])[:5]:
        print(f"  {p['formula']:<14} {p['kind_ru']:<22} {p['moles']:.4g} моль  {p['mass_g']:.4g} г")
    if s.get("confidence") is not None:
        print(f"Уверенность: {s['confidence'] * 100:.0f} %")
    for w in dict.fromkeys(d.get("warnings") or []):
        print(f"! {w}")
    paths = res.save_all()
    for k, p in paths.items():
        print(f"{k}: {p}")
    if a.open and "html" in paths:
        from .report.html import HTMLReport
        HTMLReport.open(paths["html"])
    return 0 if d["status"] in ("ok", "no_reaction") else 1


def cmd_self_test(a) -> int:
    """Quick built-in checks (no pytest needed); full suite: self_test.ps1."""
    import socket
    from .agent import Agent
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'OK' if cond else 'FAIL'}] {name}{(' - ' + extra) if extra else ''}")

    check("офлайн-защита включена", offline_guard.is_active())
    try:
        socket.create_connection(("93.184.216.34", 80), timeout=1)
        check("сетевой вызов блокируется", False)
    except offline_guard.NetworkBlockedError:
        check("сетевой вызов блокируется", True)
    except OSError as e:
        check("сетевой вызов блокируется", False, str(e))
    ag = Agent()
    check("база загружена", len(ag.db.species) > 1000, f"{len(ag.db.species)} частиц")
    r = ag.predict(reagents=[{"formula": "NaOH", "moles": 0.05, "phase": "aq"},
                             {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
                   options={"accuracy": "fast"}).data
    check("NaOH + HCl -> NaCl + H2O", r["status"] == "ok" and r["products"][0]["formula"] == "NaCl")
    r = ag.predict(reagents=[{"formula": "BaCl2", "moles": 0.02, "phase": "aq"},
                             {"formula": "Na2SO4", "moles": 0.02, "phase": "aq"}],
                   options={"accuracy": "fast"}).data
    check("BaCl2 + Na2SO4 -> BaSO4", r["products"][0]["formula"] == "BaSO4")
    r = ag.predict(reagents=[{"formula": "Cu", "moles": 0.02, "phase": "s"},
                             {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
                   options={"accuracy": "fast"}).data
    check("Cu + HCl: реакции нет", r["status"] == "no_reaction")
    r2 = ag.predict(reagents=[{"formula": "Cu", "moles": 0.02, "phase": "s"},
                              {"formula": "HCl", "moles": 0.05, "phase": "aq"}],
                    options={"accuracy": "fast"}).data
    check("детерминизм", r["input_hash"] == r2["input_hash"] and r["products"] == r2["products"])
    if a.benchmark:
        from .benchmark import evaluate, load_reference
        res = evaluate(ag, load_reference())
        check("Accuracy@3 >= 85 %", res["accuracy_at_k"] >= 0.85,
              f"{res['accuracy_at_k'] * 100:.1f} % на {res['n_in_scope']} реакциях")
    print("Итог:", "OK" if ok else "ЕСТЬ ОШИБКИ")
    return 0 if ok else 1


def cmd_benchmark(a) -> int:
    from .agent import Agent
    from .benchmark import evaluate, load_reference
    res = evaluate(Agent(), load_reference(Path(a.reference) if a.reference else None), k=a.k)
    def pc(x):
        return f"{x * 100:.1f}".replace(".", ",")
    t = f"{res['time_s']:.1f}".replace(".", ",")
    print(f"Accuracy@{res['k']}: {pc(res['accuracy_at_k'])} % ({res['n_in_scope']} реакций в области "
          f"применимости, всего {res['n_total']}), время {t} с")
    for c, v in sorted(res["by_category"].items()):
        print(f"  {c:<16} {pc(v):>5} %")
    if a.verbose:
        for r in res["rows"]:
            if not r["ok"] and r["in_scope"]:
                print(f"  промах {r['id']}: ожидалось {r['expected']}, top-{a.k}: {r['top']} ({r['status']})")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def cmd_databases(_a) -> int:
    from .energy.database import get_db
    print(json.dumps(get_db().summary(), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    ap = argparse.ArgumentParser(prog="chem-agent", description="Локальный офлайн-предсказатель продуктов неорганических реакций")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict", help="расчет реакции")
    p.add_argument("--input", "-i", help="JSON-файл запроса")
    p.add_argument("--reagents", "-r", help='реагенты: "NaOH:2,H2SO4:1" (моль)')
    p.add_argument("--phase", help="фаза реагентов из --reagents (aq, s, l, g)")
    p.add_argument("--temp", type=float, help="температура, K")
    p.add_argument("--pressure", type=float, help="давление, атм")
    p.add_argument("--volume", type=float, help="объем, л")
    p.add_argument("--solvent", help="water или none")
    p.add_argument("--output", "-o", help="форматы: json,html,markdown")
    p.add_argument("--output-dir", help="папка для отчетов")
    p.add_argument("--accuracy", choices=["fast", "balanced", "accurate"])
    p.add_argument("--theme", choices=["light", "dark"])
    p.add_argument("--no-uncertainty", action="store_true")
    p.add_argument("--open", action="store_true", help="открыть HTML-отчет в браузере")
    p.set_defaults(fn=cmd_predict)
    s = sub.add_parser("self-test", help="быстрая самопроверка")
    s.add_argument("--offline", action="store_true", help="(всегда офлайн; флаг для совместимости)")
    s.add_argument("--benchmark", action="store_true", help="также прогнать эталон")
    s.set_defaults(fn=cmd_self_test)
    b = sub.add_parser("benchmark", help="Accuracy@k на эталонных реакциях")
    b.add_argument("--k", type=int, default=3)
    b.add_argument("--reference")
    b.add_argument("--json")
    b.add_argument("--verbose", "-v", action="store_true")
    b.set_defaults(fn=cmd_benchmark)
    sub.add_parser("databases", help="сводка по локальной базе").set_defaults(fn=cmd_databases)
    sub.add_parser("version", help="версия").set_defaults(fn=lambda _a: print(f"chem-agent {__version__}") or 0)
    a = ap.parse_args(argv)
    try:
        return int(a.fn(a) or 0)
    except Exception as e:  # noqa: BLE001
        from .parser.validator import ValidationError
        if isinstance(e, (ValidationError, FileNotFoundError, ValueError)):
            print(f"Ошибка: {e}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
