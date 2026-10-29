"""Запросы к внешним базам (W-01): PubChem первым, NIST WebBook вторым. Кэш в data/external/.

Используется только при подготовке данных (CLI, скрипты), не внутри Agent.predict:
desktop-ядро остается офлайн. При включенной офлайн-защите сеть не трогаем, отдаем кэш.

Результат fetch() всегда словарь со status:
  ok      - данные есть (source, molecular_weight, name, ...)
  unknown - данных нет; reason: not_found | network: ... | offline
Неудача пишет в кэш {"error": "no_data", ...} и в data/coverage_report.json (ТЗ п. 7.3).

Живет вне пакета chem_agent: ядро не импортирует сетевые модули (tests/test_offline.py).

CLI: python scripts/fetch_external.py CaSO4 NaCl [--force]
"""
from __future__ import annotations

import argparse
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from chem_agent.parser.formula import FormulaError, parse_formula  # noqa: E402
from chem_agent.utils import offline_guard  # noqa: E402
from chem_agent.utils.paths import PROJECT_DIR  # noqa: E402

EXTERNAL_DIR = PROJECT_DIR / "data" / "external"
COVERAGE_FILE = PROJECT_DIR / "data" / "coverage_report.json"

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PUBCHEM_PROPS = "MolecularWeight,IUPACName"
NIST = "https://webbook.nist.gov/cgi/cbook.cgi"
USER_AGENT = "chem-agent/2.5 (offline inorganic predictor; data preparation)"
TIMEOUT_S = 15.0
RETRY_NETWORK_AFTER_S = 24 * 3600  # сетевую ошибку из кэша перепроверяем не чаще раза в сутки


class RateLimiter:
    """Не чаще rate запросов в секунду (PubChem: 5/с без ключа)."""

    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = self._next
            self._next = now + self.interval


_PUBCHEM_LIMIT = RateLimiter(5.0)
_NIST_LIMIT = RateLimiter(1.0)


class NotFound(Exception):
    pass


def _http_get(url: str, timeout: float = TIMEOUT_S) -> tuple[int, bytes]:
    """GET -> (HTTP-код, тело). Сетевые сбои - исключение URLError/OSError."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cache_path(formula: str) -> Path:
    # Запрещенные в именах Windows символы -> "_"; "+", "·", скобки допустимы
    return EXTERNAL_DIR / (re.sub(r'[<>:"/\\|?*]', "_", formula) + ".json")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    tmp.replace(path)


# ----------------------------------------------------------------------------- sources
def _pubchem_props(url: str) -> list[dict]:
    _PUBCHEM_LIMIT.wait()
    code, body = _http_get(url)
    if code == 404:
        raise NotFound(url)
    if code != 200:
        raise OSError(f"PubChem HTTP {code}")
    return json.loads(body.decode("utf-8"))["PropertyTable"]["Properties"]


def _mw_matches(found: float, formula: str) -> bool:
    """Поиск по имени ловит синонимы (\"Xq2\" -> лекарство XQ2): сверяем M с формулой."""
    expected = parse_formula(formula).molar_mass()
    return abs(found - expected) <= max(0.005 * expected, 0.05)


def from_pubchem(formula: str) -> dict:
    """Поиск по имени (ТЗ п. 7.1), затем по формуле (fastformula) для нейтральных частиц."""
    q = urllib.parse.quote(formula, safe="")
    url = f"{PUBCHEM}/name/{q}/property/{PUBCHEM_PROPS}/JSON"
    try:
        props = [p for p in _pubchem_props(url) if _mw_matches(float(p["MolecularWeight"]), formula)]
    except NotFound:
        props = []
    if not props:
        comp = parse_formula(formula)
        if comp.charge or any(n != int(n) for n in comp.as_dict.values()):
            raise NotFound(formula)
        url = f"{PUBCHEM}/fastformula/{urllib.parse.quote(comp.hill())}/property/{PUBCHEM_PROPS}/JSON"
        props = _pubchem_props(url)
    if not props:
        raise NotFound(formula)
    p = props[0]
    return {"source": "pubchem", "cid": p.get("CID"), "molecular_weight": float(p["MolecularWeight"]),
            "name": p.get("IUPACName"), "n_candidates": len(props), "query": url}


_RE_TITLE = re.compile(r"<title>([^<]*)</title>")
_RE_MW = re.compile(r"Molecular weight</a>:</strong>\s*([0-9.]+)")
_RE_ID = re.compile(r'href="/cgi/cbook\.cgi\?ID=([A-Z0-9]+)&amp;Units=SI">([^<]+)<')


def from_nist(formula: str) -> dict:
    """NIST WebBook, HTML. Одна страница -> имя и M; список -> кандидаты, M считаем по формуле."""
    url = f"{NIST}?{urllib.parse.urlencode({'Formula': formula, 'NoIon': 'on', 'Units': 'SI'})}"
    _NIST_LIMIT.wait()
    code, body = _http_get(url)
    if code != 200:
        raise OSError(f"NIST HTTP {code}")
    html = body.decode("utf-8", errors="replace")
    title = (_RE_TITLE.search(html) or [None, ""])[1].strip()
    if "Not Found" in title:
        raise NotFound(formula)
    mw = _RE_MW.search(html)
    if mw:
        return {"source": "nist", "molecular_weight": float(mw.group(1)), "name": title, "query": url}
    cands = [{"nist_id": i, "name": n.strip()} for i, n in _RE_ID.findall(html)][:10]
    if not cands:
        raise NotFound(formula)
    mw_calc = round(parse_formula(formula).molar_mass(), 3)
    return {"source": "nist", "molecular_weight": mw_calc, "molecular_weight_note": "computed",
            "name": None, "candidates": cands, "query": url}


SOURCES = {"pubchem": from_pubchem, "nist": from_nist}


# ----------------------------------------------------------------------------- coverage
def _update_coverage(formula: str, record: dict | None) -> None:
    """record=None - формула найдена, убираем из missing."""
    try:
        cov = json.loads(COVERAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cov = {"missing": {}}
    missing = cov.setdefault("missing", {})
    if record is None:
        if formula not in missing:
            return
        missing.pop(formula)
    else:
        missing[formula] = record
    cov["generated_at"] = _now()
    cov["n_missing"] = len(missing)
    _write_json(COVERAGE_FILE, cov)


# ----------------------------------------------------------------------------- public API
def _unknown(formula: str, reason: str, **extra) -> dict:
    return {"formula": formula, "status": "unknown", "reason": reason, **extra}


def fetch(formula: str, *, force: bool = False, sources=("pubchem", "nist")) -> dict:
    try:
        parse_formula(formula)
    except FormulaError as e:
        return _unknown(formula, f"bad_formula: {e}")
    path = cache_path(formula)
    if path.exists() and not force:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if "error" not in cached:
            return {**cached, "status": "ok", "cached": True}
        age = time.time() - path.stat().st_mtime
        if cached.get("reason") == "not_found" or age < RETRY_NETWORK_AFTER_S:
            return _unknown(formula, cached.get("reason", "no_data"), cached=True)

    if offline_guard.is_active():
        _update_coverage(formula, {"reason": "offline", "when": _now()})
        return _unknown(formula, "offline")

    tried, net_errors = [], []
    for name in sources:
        tried.append(name)
        try:
            data = SOURCES[name](formula)
        except NotFound:
            continue
        except (OSError, ValueError, KeyError) as e:  # URLError - подкласс OSError
            net_errors.append(f"{name}: {e}")
            continue
        record = {"formula": formula, **data, "fetched_at": _now()}
        _write_json(path, record)
        _update_coverage(formula, None)
        return {**record, "status": "ok", "cached": False}

    reason = "network: " + "; ".join(net_errors) if net_errors else "not_found"
    _write_json(path, {"formula": formula, "error": "no_data", "reason": reason,
                       "sources_tried": tried, "fetched_at": _now()})
    _update_coverage(formula, {"reason": reason, "sources_tried": tried, "when": _now()})
    return _unknown(formula, reason)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Внешние данные (PubChem, NIST WebBook) в data/external/")
    ap.add_argument("formulas", nargs="+")
    ap.add_argument("--force", action="store_true", help="игнорировать кэш")
    args = ap.parse_args(argv)
    bad = 0
    for f in args.formulas:
        r = fetch(f, force=args.force)
        if r["status"] == "ok":
            print(f"{f}: {r['source']} M = {r.get('molecular_weight')} {r.get('name') or ''}"
                  f"{' (кэш)' if r.get('cached') else ''}")
        else:
            bad += 1
            print(f"{f}: unknown ({r['reason']})")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
