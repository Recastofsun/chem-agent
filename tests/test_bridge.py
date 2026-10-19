import pytest
from chem_agent.api.bridge import Bridge, APP_VERSION

@pytest.fixture
def bridge():
    return Bridge()

def test_ping_ok(bridge):
    res = bridge.ping()
    assert res["status"] == "ok"
    assert res["error"] is None
    assert res["data"]["message"] == "pong"
    assert res["data"]["app_version"] == APP_VERSION

def test_get_version_ok(bridge):
    res = bridge.get_version()
    assert res["status"] == "ok"
    assert res["error"] is None
    assert res["data"]["version"] == APP_VERSION

def test_predict_not_implemented(bridge):
    res = bridge.predict(["HCl"])
    assert res["status"] == "error"
    assert res["data"] is None
    assert res["error"]["code"] == "NOT_IMPLEMENTED"

def test_ok_shape(bridge):
    res = bridge._ok({"test": 1})
    assert res == {"status": "ok", "data": {"test": 1}, "error": None}

def test_err_shape(bridge):
    res = bridge._err("TEST_CODE", "Test message", "Test details")
    assert res == {
        "status": "error",
        "data": None,
        "error": {"code": "TEST_CODE", "message": "Test message", "details": "Test details"}
    }