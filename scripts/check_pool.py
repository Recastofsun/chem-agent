"""Три прохода проверки пула (ТЗ 13.1): python scripts/check_pool.py [data/pool_100.json] [--offline]

1. Покрытие: каждая формула реагентов и ожидаемых уравнений разбирается и есть в crc.db (в любой фазе
   или через ионы). Нет - запись в coverage_report.json (как у fetch_external).
2. Внешняя проверка: формулы без записи в базе - fetch_external (PubChem -> NIST, кэш data/external/).
   Подтверждает, что вещество существует; термодинамики PubChem не дает, поэтому реакция остается unknown.
   --offline - проход 2 пропускается.
3. Ядро против ожиданий (scripts/run_pool.py): несовпадения -> data/pool_disputed.json с причиной.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chem_agent.energy.database import get_db  # noqa: E402
from chem_agent.parser.formula import parse_formula  # noqa: E402
from chem_agent.search.staged_balancer import dissociate  # noqa: E402
from scripts import fetch_external as fe  # noqa: E402
from scripts.run_pool import run  # noqa: E402

NITRATES_HOT = ("Ожидание генератора спорно: при T + 200 K в открытой системе (P -> 0) равновесие дает вторичное "
                "разложение - NO2 -> NO + O2, разложение нитрита, пары щелочного металла. Учебное уравнение описывает "
                "первичную стадию. Ограничение модели открытой системы (LIMITATIONS).")
# Разбор несовпадений, которые остаются после исправлений ядра (W-15). Ключ - id реакции.
REASONS = {
    "r11": "Нет SnCl6-2 в базе: Sn(IV) в 0,1 М HCl выпадает как SnO2. Учебное уравнение предполагает "
           "концентрированную HCl и хлорокомплекс олова. Пробел данных.",
    "c10": "FeCl3 + KSCN: в базе один комплекс FeSCN+2 (lg β из complex_constants в расчете не участвует), "
           "равновесие уводит в Fe(SCN)3 и гидролиз; известная проблема h049.",
    "d10": "Нет Pb(NO3)2(тв) в базе: известна только ΔfH = -451,9 кДж/моль, ΔfG и S° в открытых источниках "
           "не найдены. Пробел данных, status unknown.",
    "g03": "По данным CRC N2O4(ж) при 298 K стабильнее газа на 0,4 кДж/моль (Tкип 294 K): ядро дает жидкий "
           "N2O4. Погрешность данных больше разницы; ожидание (NO2/N2O4 газ) верно.",
    # пул 1000 (W-16)
    "R135": "Sn + CuSO4: ядро дает Sn(IV) (SnO2), учебник - SnSO4. Cu2+ термодинамически окисляет Sn2+ "
            "(E Sn4+/Sn2+ = 0,15 В < 0,34 В), гидролиз Sn(IV) до SnO2 выгоден; кинетику окисления Sn(II) ядро не знает.",
    "R136": "То же, что R135 (другая концентрация).",
    "D056": "KClO4 при 1100 K в открытой системе: давление пара KCl 4e-3 бар выше порога 1e-3 бар, KCl уходит в газ. "
            "Граница модели испарения в открытой системе.",
    "G031": "Mn + O2 при 700 K: ядро дает Mn2O3, ожидалось MnO2. Граница MnO2/Mn2O3 (Kp = 1 бар около 760-800 K) "
            "в пределах погрешности данных при остаточном давлении O2 в закрытом объеме.",
    "G115": "ZnS + HCl в закрытом сосуде 1 л: ZnS растворяется частично (K ~ 1e-4), H2S меньше растворимости и "
            "остается в растворе. Учебное уравнение со стрелкой предполагает открытый сосуд.",
    "G116": "То же, что G115 (HBr).",
    "G117": "ZnS + H2SO4 в закрытом сосуде: растворение ZnS ниже порога реакции (см. G115).",
    "P033": "Осадок PbC2O4 в базе есть (Ksp = 10^-9.77), но из-за высокой концентрации Na+ и NO3- ранкер ставит соль NaNO3 на первое место по массе. Термодинамически осадок есть.",
    "P034": "То же, что P033, но с KNO3.",
    **{k: NITRATES_HOT for k in ("D067", "D068", "D071", "D072", "D073", "D074", "D076")},
}


def formulas_of(rx) -> set:
    out = {r["formula"] for r in rx["reagents"]}
    for eq in [rx["expected_equation"]] + rx.get("accept_equations", []):
        for side in eq.split("->"):
            for t in side.split(" + "):
                t = t.strip().rstrip("↓↑")
                if t:
                    out.add(t.split(" ", 1)[1] if t.split(" ")[0].isdigit() else t)
    return out


def coverage(pool) -> dict:
    db = get_db()
    keys = {s.key for s in db.species}
    missing = {}
    for rx in pool:
        for f in formulas_of(rx):
            try:
                c = parse_formula(f)
            except Exception as e:  # noqa: BLE001
                missing.setdefault(f, []).append(f"{rx['id']}: формула не разбирается ({e})")
                continue
            if c.key in keys or all(k in keys for k in dissociate(c.key)) and dissociate(c.key) != {c.key: 1.0}:
                continue
            missing.setdefault(f, []).append(rx["id"])
        for r in rx["reagents"]:  # твердый/жидкий/газовый реагент нужен именно в своей фазе
            if r["phase"] in ("s", "l", "g") and not db.find_formula(r["formula"], r["phase"]):
                missing.setdefault(f"{r['formula']}({r['phase']})", []).append(rx["id"])
    return missing


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]).resolve() if args else ROOT / "data" / "pool_100.json"
    pool = json.loads(path.read_text(encoding="utf-8"))
    missing = coverage(pool)
    print(f"Проход 1: формул без данных в базе - {len(missing)}: {', '.join(sorted(missing)) or 'нет'}")
    ext = {}
    if "--offline" not in sys.argv:
        for f in sorted(missing):
            ext[f] = fe.fetch(f)
            print(f"Проход 2: {f} - {ext[f]['status']} {ext[f].get('source') or ext[f].get('reason', '')}")
    cov = json.loads(fe.COVERAGE_FILE.read_text(encoding="utf-8")) if fe.COVERAGE_FILE.exists() else {}
    cov.setdefault("missing", {})
    for f, ids in missing.items():
        cov["missing"][f] = {"reason": "нет термодинамических данных в crc.db", "pool": ids,
                             "external": (ext.get(f) or {}).get("status")}
    excl = ROOT / "data" / f"{path.stem}_excluded.json"
    if excl.exists():  # реакции генератора, исключенные из пула из-за пробела данных (ТЗ 13.3)
        for rx in json.loads(excl.read_text(encoding="utf-8")):
            for f in rx.get("missing", []):
                e = cov["missing"].setdefault(f, {"reason": "нет термодинамических данных в crc.db", "pool": []})
                e["pool"] = sorted(set(e.get("pool", [])) | {rx["id"] + " (исключена)"})
    cov["n_missing"] = len(cov["missing"])
    fe.COVERAGE_FILE.write_text(json.dumps(cov, ensure_ascii=False, indent=1), encoding="utf-8")
    rep = run(path)
    disputed = [{**{k: r[k] for k in ("id", "category", "main", "expected_main", "equation", "expected_equation",
                                       "status")},
                 "reason": REASONS.get(r["id"], "не разобрано")} for r in rep["rows"] if not r["ok"]]
    out = ROOT / "data" / f"pool_disputed{'' if path.stem == 'pool_100' else '_' + path.stem.replace('pool_', '')}.json"
    out.write_text(json.dumps(disputed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Проход 3: точность {rep['accuracy']:.1%}, расхождений {len(disputed)} -> {out.name}")


if __name__ == "__main__":
    main()
