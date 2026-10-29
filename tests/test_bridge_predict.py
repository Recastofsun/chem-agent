import pytest
from chem_agent.api.bridge import Bridge

@pytest.fixture(scope="module")
def bridge():
    """Создаем один экземпляр Bridge на все тесты (чтобы база грузилась 1 раз)."""
    b = Bridge()
    return b

def test_predict_real_core(bridge):
    """Интеграционный тест: проверяем, что ядро реально считает NaOH + HCl."""
    request_data = {
        "reagents": [
            {"formula": "NaOH", "moles": 1.0},
            {"formula": "HCl", "moles": 1.0}
        ],
        "conditions": {
            "temperature_K": 298.15,
            "pressure_atm": 1.0,
            "volume_L": 1.0
        }
    }
    
    res = bridge.predict(request_data)
    
    # 1. Проверяем статус ответа Bridge
    assert res["status"] == "ok"
    assert res["error"] is None
    
    # 2. Проверяем данные от ядра
    data = res["data"]
    assert data["status"] == "ok"
    
    # 3. Проверяем, что уравнение найдено
    equations = data["balanced_equations"]
    assert len(equations) > 0
    eq = equations[0]
    
    assert "NaOH" in eq["equation"]
    assert "NaCl" in eq["equation"]
    assert eq["delta_G_kJ_mol"] < 0  # Реакция должна быть термодинамически выгодной

def test_predict_invalid_data(bridge):
    """Ошибка валидации: ядро возвращает status=error в data (с v2.3 Agent.predict не бросает
    ValidationError), Bridge отдает ответ без исключения в JS."""
    res = bridge.predict({"reagents": [], "conditions": {}})
    assert res["status"] == "ok"
    assert res["data"]["status"] == "error"
    assert "reagents" in res["data"]["message"]