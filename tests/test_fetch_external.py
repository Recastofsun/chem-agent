"""W-01: fetch_external (PubChem -> NIST, кэш, coverage_report). Сеть подменена, реальных запросов нет."""
import json
import os
import time

import pytest

from scripts import fetch_external as fe


def _pubchem(props):
    return 200, json.dumps({"PropertyTable": {"Properties": props}}).encode()


NOT_FOUND = (404, b'{"Fault": {"Code": "PUGREST.NotFound"}}')


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Кэш во временной папке, офлайн-защита выключена только для модуля, лог URL."""
    monkeypatch.setattr(fe, "EXTERNAL_DIR", tmp_path / "external")
    monkeypatch.setattr(fe, "COVERAGE_FILE", tmp_path / "coverage_report.json")
    monkeypatch.setattr(fe.offline_guard, "is_active", lambda: False)
    monkeypatch.setattr(fe, "_PUBCHEM_LIMIT", fe.RateLimiter(1e6))
    monkeypatch.setattr(fe, "_NIST_LIMIT", fe.RateLimiter(1e6))
    calls = []

    def install(responder):
        def fake(url, timeout=fe.TIMEOUT_S):
            calls.append(url)
            return responder(url)
        monkeypatch.setattr(fe, "_http_get", fake)
    return tmp_path, calls, install


def test_pubchem_by_name_and_cache(env):
    tmp, calls, install = env
    install(lambda url: _pubchem([{"CID": 5234, "MolecularWeight": "58.44", "IUPACName": "sodium chloride"}]))
    r = fe.fetch("NaCl")
    assert r["status"] == "ok" and r["source"] == "pubchem" and r["molecular_weight"] == 58.44
    assert "/name/NaCl/property/MolecularWeight,IUPACName/JSON" in calls[0]
    assert (tmp / "external" / "NaCl.json").exists()
    r2 = fe.fetch("NaCl")
    assert r2["cached"] and len(calls) == 1


def test_name_synonym_with_wrong_mass_falls_back_to_formula(env):
    _, calls, install = env

    def resp(url):
        if "/name/" in url:  # синоним-однофамилец с чужой массой
            return _pubchem([{"CID": 1, "MolecularWeight": "573.6", "IUPACName": "drug"}])
        return _pubchem([{"CID": 24497, "MolecularWeight": "136.14", "IUPACName": "calcium sulfate"}])
    install(resp)
    r = fe.fetch("CaSO4")
    assert r["cid"] == 24497 and "/fastformula/CaO4S/" in calls[1]


def test_nist_fallback_single_page(env):
    _, _, install = env

    def resp(url):
        if "pubchem" in url:
            return NOT_FOUND
        return 200, (b"<title>sodium chloride</title>"
                     b'<a href="x">Molecular weight</a>:</strong> 58.443</li>')
    install(resp)
    r = fe.fetch("NaCl")
    assert r["source"] == "nist" and r["molecular_weight"] == 58.443


def test_nist_candidates_list_uses_computed_mass(env):
    _, _, install = env

    def resp(url):
        if "pubchem" in url:
            return NOT_FOUND
        return 200, (b"<title>Search Results</title>"
                     b'<a href="/cgi/cbook.cgi?ID=C7778189&amp;Units=SI">Calcium sulfate, anhydrous</a>')
    install(resp)
    r = fe.fetch("CaSO4")
    assert r["molecular_weight_note"] == "computed"
    assert r["molecular_weight"] == pytest.approx(136.14, abs=0.01)
    assert r["candidates"][0]["nist_id"] == "C7778189"


def test_not_found_writes_no_data_and_coverage(env):
    tmp, calls, install = env
    install(lambda url: NOT_FOUND if "pubchem" in url else (200, b"<title>Chemical Formula Not Found</title>"))
    r = fe.fetch("FeSCN+2")
    assert r["status"] == "unknown" and r["reason"] == "not_found"
    cached = json.loads((tmp / "external" / "FeSCN+2.json").read_text(encoding="utf-8"))
    assert cached["error"] == "no_data" and cached["sources_tried"] == ["pubchem", "nist"]
    cov = json.loads((tmp / "coverage_report.json").read_text(encoding="utf-8"))
    assert cov["n_missing"] == 1 and "FeSCN+2" in cov["missing"]
    n = len(calls)
    assert fe.fetch("FeSCN+2")["reason"] == "not_found" and len(calls) == n  # not_found не перезапрашиваем


def test_network_error_retried_after_ttl(env):
    tmp, calls, install = env

    def down(url):
        raise OSError("timed out")
    install(down)
    r = fe.fetch("NaCl")
    assert r["status"] == "unknown" and r["reason"].startswith("network:")
    n = len(calls)
    fe.fetch("NaCl")
    assert len(calls) == n  # в пределах суток - из кэша
    old = time.time() - fe.RETRY_NETWORK_AFTER_S - 10
    os.utime(tmp / "external" / "NaCl.json", (old, old))
    install(lambda url: _pubchem([{"CID": 5234, "MolecularWeight": "58.44", "IUPACName": "sodium chloride"}]))
    assert fe.fetch("NaCl")["status"] == "ok"
    cov = json.loads((tmp / "coverage_report.json").read_text(encoding="utf-8"))
    assert "NaCl" not in cov["missing"]


def test_offline_guard_blocks_network(env, monkeypatch):
    tmp, calls, install = env
    install(lambda url: pytest.fail("сеть при офлайн-защите"))
    monkeypatch.setattr(fe.offline_guard, "is_active", lambda: True)
    r = fe.fetch("NaCl")
    assert r == {"formula": "NaCl", "status": "unknown", "reason": "offline"}
    assert not (tmp / "external" / "NaCl.json").exists()


def test_bad_formula_no_request(env):
    _, calls, install = env
    install(lambda url: pytest.fail("запрос с невалидной формулой"))
    assert fe.fetch("Xq2")["reason"].startswith("bad_formula")


def test_cache_path_windows_safe():
    assert fe.cache_path("K4[Fe(CN)6]").name == "K4[Fe(CN)6].json"
    assert fe.cache_path('A/B:"C"').name == "A_B__C_.json"


def test_rate_limiter_spacing():
    # perf_counter: у monotonic на Windows шаг ~15 мс, тест на интервал 20 мс от этого мигал
    lim = fe.RateLimiter(20.0)
    t = time.perf_counter()
    for _ in range(4):
        lim.wait()
    assert time.perf_counter() - t >= 3 * 0.05 * 0.9
