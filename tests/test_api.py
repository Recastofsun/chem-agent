"""REST API on 127.0.0.1 (FastAPI TestClient; skipped if fastapi is not installed)."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from chem_agent.api.server import app  # noqa: E402

client = TestClient(app)


def test_health_version():
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/version").json()["version"] == "2.5.0"


def test_predict_and_reports():
    r = client.post("/predict", json={"reagents": [{"formula": "AgNO3", "moles": 0.01, "phase": "aq"},
                                                   {"formula": "NaCl", "moles": 0.01, "phase": "aq"}],
                                      "options": {"accuracy": "fast"}})
    assert r.status_code == 200
    d = r.json()
    assert d["products"][0]["formula"] == "AgCl"
    rid = d["reaction_id"]
    assert client.get(f"/report/{rid}.json").json()["reaction_id"] == rid
    html = client.get(f"/report/{rid}").text
    assert "Резюме" in html
    assert client.get("/history").json()[0]["reaction_id"] == rid


def test_validation_error():
    r = client.post("/predict", json={"reagents": [{"formula": "Qq", "moles": 1}]})
    assert r.status_code == 422


def test_databases_models_ui():
    assert client.get("/databases").json()["species"] > 1000
    assert client.get("/models").json()["ml_potential"]["available"] is False
    assert "chem-agent" in client.get("/").text


def test_non_local_rejected():
    c = TestClient(app, client=("10.0.0.5", 5000))
    assert c.get("/health").status_code == 403
